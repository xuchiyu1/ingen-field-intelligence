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
  python src/classify_llm.py --input data/field_reports.csv --save-corpus --prompt <final>
      # full corpus with the final prompt -> data/classified_corpus.csv
  python src/classify_llm.py ... --retry-flagged
      # same command again: keep earlier good rows, rerun only the flagged ones

Backends
  --backend api         Anthropic API via the SDK; requires ANTHROPIC_API_KEY (never committed)
  --backend claude-cli  Claude Code in print mode (`claude -p`), using the logged-in Claude
                        subscription. Each call runs in an empty working directory with all
                        tools disabled and no saved session, so the model sees only the
                        prompt and one report.
"""

import argparse
import csv
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:  # only needed for --backend api
    anthropic = None

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
    if not out["reason"].strip():
        return "empty reason"
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


class CliUsage:
    """Token usage from a `claude -p --output-format json` result."""
    def __init__(self, u):
        self.input_tokens = u.get("input_tokens", 0)
        self.output_tokens = u.get("output_tokens", 0)
        self.cache_read_input_tokens = u.get("cache_read_input_tokens", 0)
        self.cache_creation_input_tokens = u.get("cache_creation_input_tokens", 0)


MODELS_SEEN = set()  # actual model IDs reported by claude -p
CLI_ALIASES = {"claude-opus-5-5": "opus", "claude-sonnet-5-5": "sonnet", "claude-haiku-5-5": "haiku"}


def classify_cli(model, system_prompt, report, workdir):
    """One `claude -p` call. Returns (parsed dict or None, error, usage, cost_usd)."""
    proc = subprocess.run(
        ["claude", "-p", f"Platform: {report['platform']}\nReport: {report['text']}",
         "--system-prompt", system_prompt, "--json-schema", json.dumps(SCHEMA),
         "--output-format", "json", "--tools", "", "--no-session-persistence",
         "--model", CLI_ALIASES[model]],
        capture_output=True, text=True, cwd=workdir, timeout=300)
    try:
        d = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, f"cli output not JSON: {proc.stderr[:200]}", CliUsage({}), 0.0
    usage, cost = CliUsage(d.get("usage") or {}), d.get("total_cost_usd") or 0.0
    MODELS_SEEN.update((d.get("modelUsage") or {}).keys())
    if d.get("is_error"):
        return None, f"cli error: {str(d.get('result'))[:200]}", usage, cost
    out = d.get("structured_output")
    if out is None:
        try:
            out = json.loads(d.get("result", ""))
        except json.JSONDecodeError:
            return None, "invalid JSON", usage, cost
    error = validate(out)
    return (None if error else out), error, usage, cost


BATCH_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {"report_id": {"type": "string"}, **SCHEMA["properties"]},
        "required": ["report_id"] + SCHEMA["required"],
        "additionalProperties": False}}},
    "required": ["results"],
    "additionalProperties": False,
}


def classify_cli_batch(model, system_prompt, reports, workdir):
    """Classify several reports in one `claude -p` call (cheaper for the full corpus).
    Returns ({report_id: parsed dict}, error, usage, cost_usd)."""
    body = "\n\n".join(f"report_id: {r['report_id']}\nPlatform: {r['platform']}\nReport: {r['text']}"
                        for r in reports)
    prompt = (f"Classify each of the {len(reports)} reports below independently. "
              f"Return one result per report_id.\n\n{body}")
    proc = subprocess.run(
        ["claude", "-p", prompt, "--system-prompt", system_prompt,
         "--json-schema", json.dumps(BATCH_SCHEMA), "--output-format", "json",
         "--tools", "", "--no-session-persistence", "--model", CLI_ALIASES[model]],
        capture_output=True, text=True, cwd=workdir, timeout=900)
    try:
        d = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, f"cli output not JSON: {proc.stderr[:200]}", CliUsage({}), 0.0
    usage, cost = CliUsage(d.get("usage") or {}), d.get("total_cost_usd") or 0.0
    MODELS_SEEN.update((d.get("modelUsage") or {}).keys())
    if d.get("is_error"):
        return {}, f"cli error: {str(d.get('result'))[:200]}", usage, cost
    out = {}
    for item in (d.get("structured_output") or {}).get("results", []):
        rid = item.pop("report_id", None)
        if rid and not validate(item):
            out[rid] = item
    return out, "", usage, cost


def limit_hit(error):
    """True when the Claude subscription's usage limit stopped the call."""
    return "hit your" in error.lower() and "limit" in error.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="eval/gold_set.csv")
    ap.add_argument("--split", choices=["tuning", "heldout"], help="gold-set split to run")
    ap.add_argument("--prompt", default="classify_v1")
    ap.add_argument("--model", default="claude-opus-5-5", choices=sorted(PRICES))
    ap.add_argument("--backend", choices=["api", "claude-cli"], default="api")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=1,
                    help="claude-cli only: reports per call (use for the full corpus)")
    ap.add_argument("--save-corpus", action="store_true",
                    help="also write data/classified_corpus.csv (reports + predictions)")
    ap.add_argument("--retry-flagged", action="store_true",
                    help="reuse the earlier results file; rerun only reports that were flagged")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(ROOT / args.input, encoding="utf-8")))
    if args.split:
        rows = [r for r in rows if r.get("split") == args.split]
    if args.limit:
        rows = rows[:args.limit]
    system_prompt = (ROOT / "prompts" / f"{args.prompt}.md").read_text(encoding="utf-8")

    tag = (Path(args.input).stem + (f"_{args.split}" if args.split else "")
           + (f"_batch{args.batch_size}" if args.batch_size > 1 else ""))
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_csv = out_dir / f"llm_{args.prompt}_{tag}.csv"
    out_log = out_csv.with_suffix(".json")
    previous, prev_log = {}, None
    if args.retry_flagged:
        previous = {r["report_id"]: r for r in csv.DictReader(open(out_csv, encoding="utf-8"))
                    if not r["flag"]}
        prev_log = json.loads(out_log.read_text())
    todo = [r for r in rows if r["report_id"] not in previous]
    print(f"{len(todo)} reports to classify ({len(previous)} kept from the earlier run)")

    client = anthropic.Anthropic() if args.backend == "api" else None
    workdir = tempfile.mkdtemp(prefix="classify_")  # empty cwd for claude -p
    cli_cost = 0.0
    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    results, flagged = [], 0
    started = time.time()
    if args.backend == "claude-cli" and args.batch_size > 1:
        for start in range(0, len(todo), args.batch_size):
            chunk = todo[start:start + args.batch_size]
            got, error, usage, c = classify_cli_batch(args.model, system_prompt, chunk, workdir)
            if error.startswith("cli error: Failed to authenticate"):
                raise SystemExit("Claude Code is not logged in: run `claude`, then /login")
            if limit_hit(error):
                print(f"stopping: {error}. Rerun with --retry-flagged after the reset.")
                break
            cli_cost += c
            for k in totals:
                totals[k] += getattr(usage, k, 0) or 0
            for report in chunk:   # anything missing from the batch is retried alone
                out = got.get(report["report_id"])
                err = error or "missing from batch"
                if not out:
                    out, err, usage, c = classify_cli(args.model, system_prompt, report, workdir)
                    cli_cost += c
                    for k in totals:
                        totals[k] += getattr(usage, k, 0) or 0
                flagged += not out
                results.append({
                    "report_id": report["report_id"],
                    "pred_category": out["category"] if out else "",
                    "pred_severity": out["severity"] if out else "",
                    "pred_root_cause_stated": out["root_cause_stated"] if out else "",
                    "confidence": out["confidence"] if out else "",
                    "reason": out["reason"] if out else "",
                    "flag": "" if out else err,
                })
            print(f"[{min(start + args.batch_size, len(todo))}/{len(todo)}] batch done, "
                  f"{flagged} flagged so far", flush=True)
        rows_iter = []
    else:
        rows_iter = todo
    for i, report in enumerate(rows_iter, 1):
        out, error = None, ""
        for _attempt in range(2):  # one retry on invalid output
            if args.backend == "claude-cli":
                out, error, usage, c = classify_cli(args.model, system_prompt, report, workdir)
                cli_cost += c
                if error.startswith("cli error: Failed to authenticate"):
                    raise SystemExit("Claude Code is not logged in: run `claude`, then /login")
                if limit_hit(error):
                    break
                for k in totals:
                    totals[k] += getattr(usage, k, 0) or 0
                if out:
                    break
                continue
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
        if limit_hit(error):
            print(f"stopping: {error}. Rerun with --retry-flagged after the reset.")
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
        print(f"[{i}/{len(todo)}] {report['report_id']} -> "
              f"{results[-1]['pred_category'] or 'FLAGGED: ' + error}")

    p_in, p_out = PRICES[args.model]
    cost = cli_cost if args.backend == "claude-cli" else (totals["input_tokens"] * p_in
            + totals["cache_read_input_tokens"] * p_in * 0.10
            + totals["cache_creation_input_tokens"] * p_in * 1.25
            + totals["output_tokens"] * p_out) / 1e6

    blank = dict.fromkeys(["pred_category", "pred_severity", "pred_root_cause_stated",
                           "confidence", "reason"], "")
    done = {**previous, **{r["report_id"]: r for r in results}}
    results = [done.get(r["report_id"]) or {"report_id": r["report_id"], **blank, "flag": "not run"}
               for r in rows]
    flagged = sum(bool(r["flag"]) for r in results)
    models = set(MODELS_SEEN)
    seconds = time.time() - started
    if prev_log:   # report the whole corpus: earlier run + this rerun
        for k in totals:
            totals[k] += prev_log["tokens"].get(k, 0)
        cost += prev_log["estimated_cost_usd"]
        seconds += prev_log["seconds"]
        models |= set(m for m in prev_log["model"].split(", ") if m)

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    log = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "model": args.model if args.backend == "api" else ", ".join(sorted(models)),
           "backend": args.backend,
           "prompt_version": args.prompt, "input": args.input,
           "split": args.split, "batch_size": args.batch_size,
           "n_reports": len(rows), "n_flagged": flagged,
           "n_rerun": len(todo) if args.retry_flagged else None,
           "tokens": totals, "estimated_cost_usd": round(cost, 4),
           "cost_note": ("API list price" if args.backend == "api" else
                         "claude -p equivalent cost; billed to the Claude subscription, not charged"),
           "seconds": round(seconds, 1)}
    out_log.write_text(json.dumps(log, indent=2))

    if args.save_corpus:
        by_id = {r["report_id"]: r for r in results}
        corpus = [{**report, **{k: v for k, v in by_id[report["report_id"]].items()
                                if k != "report_id"},
                   "prompt_version": args.prompt, "model": log["model"]}
                  for report in rows]
        with open(ROOT / "data/classified_corpus.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(corpus[0]))
            w.writeheader()
            w.writerows(corpus)
        print(f"wrote data/classified_corpus.csv ({len(corpus)} rows)")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
