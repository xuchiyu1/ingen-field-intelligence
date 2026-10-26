"""Classify field reports with an LLM using the versioned taxonomy prompt.

Each report is sent with prompts/<prompt>.md as a cached system prompt. The
response is constrained to a JSON schema (category, severity,
root_cause_stated, reason, confidence) and validated again on arrival;
invalid output is retried once and then flagged.

Outputs
  results/llm_<prompt>_<input>.csv     one row per report
  results/llm_<prompt>_<input>.json    run log: model, prompt version, tokens, cost

Usage
  python src/classify_llm.py --input eval/gold_set.csv --split tuning
  python src/classify_llm.py --input eval/gold_set.csv --split heldout   # run ONCE, final prompt only
  python src/classify_llm.py --input data/field_reports.csv --limit 5   # smoke test

Requires ANTHROPIC_API_KEY (never committed).
"""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = ["H1", "H2", "H3", "H4", "S1", "S2", "S3", "S4", "S5",
              "E1", "E2", "E3", "U1", "U2", "NO_INCIDENT"]

# USD per million tokens: (input, output). Cache reads bill at 10% of input,
# 5-minute cache writes at 125%.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "severity": {"type": "integer", "enum": [1, 2, 3, 4]},
        "root_cause_stated": {"type": "boolean"},
        "reason": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["category", "severity", "root_cause_stated", "reason", "confidence"],
    "additionalProperties": False,
}


def validate(out):
    """Re-check the schema locally; returns an error message or ''."""
    if set(out) != set(SCHEMA["required"]):
        return f"fields {sorted(out)}"
    if out["category"] not in CATEGORIES:
        return f"category {out['category']!r}"
    if out["severity"] not in (1, 2, 3, 4):
        return f"severity {out['severity']!r}"
    if not isinstance(out["root_cause_stated"], bool):
        return "root_cause_stated not boolean"
    if out["confidence"] not in ("high", "medium", "low"):
        return f"confidence {out['confidence']!r}"
    return ""


def classify(client, model, system_prompt, report):
    """One API call. Returns (parsed dict or None, error, usage)."""
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content":
                   f"Platform: {report['platform']}\nReport: {report['text']}"}],
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    usage = response.usage
    if response.stop_reason == "refusal":
        return None, "refusal", usage
    if response.stop_reason == "max_tokens":
        return None, "max_tokens", usage
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return None, "invalid JSON", usage
    error = validate(out)
    return (None if error else out), error, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="eval/gold_set.csv")
    ap.add_argument("--split", choices=["tuning", "heldout"], help="gold-set split to run")
    ap.add_argument("--prompt", default="classify_v1")
    ap.add_argument("--model", default="claude-opus-5-5", choices=sorted(PRICES))
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(ROOT / args.input, encoding="utf-8")))
    if args.split:
        rows = [r for r in rows if r.get("split") == args.split]
    if args.limit:
        rows = rows[:args.limit]
    system_prompt = (ROOT / "prompts" / f"{args.prompt}.md").read_text(encoding="utf-8")

    client = anthropic.Anthropic()
    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    results, flagged = [], 0
    started = time.time()
    for i, report in enumerate(rows, 1):
        out, error = None, ""
        for _attempt in range(2):  # one retry on invalid output
            try:
                out, error, usage = classify(client, args.model, system_prompt, report)
            except anthropic.RateLimitError:
                time.sleep(30)
                continue
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    time.sleep(5)
                    continue
                raise
            for k in totals:
                totals[k] += getattr(usage, k, 0) or 0
            if out:
                break
        if not out:
            flagged += 1
        results.append({
            "report_id": report["report_id"],
            "pred_category": out["category"] if out else "",
            "pred_severity": out["severity"] if out else "",
            "pred_root_cause_stated": out["root_cause_stated"] if out else "",
            "confidence": out["confidence"] if out else "",
            "reason": out["reason"] if out else "",
            "flag": error if not out else "",
        })
        print(f"[{i}/{len(rows)}] {report['report_id']} -> "
              f"{results[-1]['pred_category'] or 'FLAGGED: ' + error}")

    p_in, p_out = PRICES[args.model]
    cost = (totals["input_tokens"] * p_in
            + totals["cache_read_input_tokens"] * p_in * 0.10
            + totals["cache_creation_input_tokens"] * p_in * 1.25
            + totals["output_tokens"] * p_out) / 1e6

    tag = Path(args.input).stem + (f"_{args.split}" if args.split else "")
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / f"llm_{args.prompt}_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    log = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "model": args.model, "prompt_version": args.prompt, "input": args.input,
           "split": args.split, "n_reports": len(rows), "n_flagged": flagged,
           "tokens": totals, "estimated_cost_usd": round(cost, 4),
           "seconds": round(time.time() - started, 1)}
    (out_dir / f"llm_{args.prompt}_{tag}.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
