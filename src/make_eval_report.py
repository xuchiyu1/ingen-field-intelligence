"""Build W02_Evaluation_Report.docx from the gold set and prediction files.

Reads
  eval/gold_set.csv                                   hand labels (held-out split)
  results/llm_<prompt>_gold_set_heldout.csv + .json   final LLM run and its run log
  results/baseline_keyword_heldout.csv                keyword baseline
  results/baseline_tfidf_heldout.csv                  TF-IDF baseline (optional)
  results/llm_<prompt>_gold_set_heldout_errors.csv    error causes filled in by hand (optional)

Usage: python src/make_eval_report.py --prompt classify_v1 [--review-floor 0.8]
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from docx import Document
from docx.shared import Pt
from sklearn.metrics import (accuracy_score, cohen_kappa_score,
                             precision_recall_fscore_support)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def read(path):
    return list(csv.DictReader(open(path, encoding="utf-8"))) if path.exists() else None


def table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for cell, h in zip(t.rows[0].cells, header):
        cell.text = h
    for row in rows:
        for cell, v in zip(t.add_row().cells, row):
            cell.text = str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="classify_v1")
    ap.add_argument("--review-floor", type=float, default=0.8,
                    help="minimum acceptable accuracy for a confidence band")
    args = ap.parse_args()

    gold_all = read(ROOT / "eval/gold_set.csv")
    gold = {r["report_id"]: r for r in gold_all
            if r["split"] == "heldout" and r["label_category"].strip()}
    llm_path = RESULTS / f"llm_{args.prompt}_gold_set_heldout.csv"
    llm = read(llm_path)
    if not gold or llm is None:
        sys.exit("need labelled held-out gold rows and " + str(llm_path.relative_to(ROOT)))
    llm = {r["report_id"]: r for r in llm}
    run_log = json.loads(llm_path.with_suffix(".json").read_text())

    def acc(preds):
        ids = [i for i in gold if preds.get(i)]
        return accuracy_score([gold[i]["label_category"].strip() for i in ids],
                              [preds[i] for i in ids]), len(ids)

    systems = [("LLM (" + args.prompt + ", " + run_log["model"] + ")",
                {i: r["pred_category"] for i, r in llm.items()})]
    for name in ("keyword", "tfidf"):
        rows = read(RESULTS / f"baseline_{name}_heldout.csv")
        if rows:
            systems.append((f"{name} baseline", {r["report_id"]: r["pred_category"] for r in rows}))

    ids = [i for i in gold if llm.get(i, {}).get("pred_category")]
    y_true = [gold[i]["label_category"].strip() for i in ids]
    y_pred = [llm[i]["pred_category"] for i in ids]
    labels = sorted(set(y_true) | set(y_pred))
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("W02 Evaluation Report: LLM Incident Classifier", 0)
    doc.add_paragraph("inGen Dynamics · Applied AI Analyst Intern · Chiyu Xu")

    doc.add_heading("1. Result on the held-out gold set", 1)
    doc.add_paragraph(
        f"All numbers are from the {len(gold)} held-out gold reports, hand-labelled from the "
        "Taxonomy Guide and never used for prompt tuning. The held-out split was run once, "
        "with the final prompt.")
    table(doc, ["System", "Accuracy", "Reports scored"],
          [(name, f"{a:.1%}", n) for name, preds in systems for a, n in [acc(preds)]])

    doc.add_heading("2. Per-category results (LLM)", 1)
    table(doc, ["Category", "Precision", "Recall", "F1", "Gold count"],
          [(l, f"{pi:.2f}", f"{ri:.2f}", f"{fi:.2f}", si)
           for l, pi, ri, fi, si in zip(labels, p, r, f, s)])
    confusions = Counter((t, q) for t, q in zip(y_true, y_pred) if t != q).most_common(8)
    doc.add_paragraph("Most frequent confusions (gold → predicted): " + (
        "; ".join(f"{t} → {q} ({n})" for (t, q), n in confusions) or "none"))

    sev = [(gold[i]["label_severity"].strip(), str(llm[i]["pred_severity"]))
           for i in ids if gold[i]["label_severity"].strip() and llm[i]["pred_severity"]]
    if sev:
        exact = sum(a == b for a, b in sev) / len(sev)
        within = sum(abs(int(a) - int(b)) <= 1 for a, b in sev) / len(sev)
        doc.add_paragraph(f"Severity agreement: exact {exact:.1%}, within one level {within:.1%} "
                          f"(n = {len(sev)}).")

    doc.add_heading("3. Label agreement (gold set)", 1)
    pairs = [(g["label_category"].strip(), g["round2_category"].strip())
             for g in gold_all if g["round2_category"].strip() and g["label_category"].strip()]
    if len(pairs) >= 10:
        a, b = zip(*pairs)
        doc.add_paragraph(f"Cohen's kappa on {len(pairs)} double-labelled reports: "
                          f"{cohen_kappa_score(a, b):.2f} (raw agreement "
                          f"{sum(x == y for x, y in pairs) / len(pairs):.1%}).")
    else:
        doc.add_paragraph("Second-round labels not yet complete.")

    doc.add_heading("4. Human-review threshold", 1)
    bands = []
    for band in ("high", "medium", "low"):
        hits = [gold[i]["label_category"].strip() == llm[i]["pred_category"]
                for i in ids if llm[i]["confidence"] == band]
        if hits:
            bands.append((band, sum(hits) / len(hits), len(hits)))
    table(doc, ["Confidence", "Accuracy", "Reports", "Share"],
          [(b, f"{a:.1%}", n, f"{n / len(ids):.0%}") for b, a, n in bands])
    below = [b for b, a, _ in bands if a < args.review_floor]
    doc.add_paragraph(
        f"Accuracy floor: {args.review_floor:.0%}. " + (
            f"Bands below the floor ({', '.join(below)}) are routed to human review, "
            f"{sum(n for b, _, n in bands if b in below) / len(ids):.0%} of outputs."
            if below else "Every confidence band meets the floor; no routing threshold is needed "
                          "on this evidence."))

    doc.add_heading("5. Error analysis by cause", 1)
    err_rows = read(llm_path.with_name(llm_path.stem + "_errors.csv"))
    causes = Counter(e["error_cause"].strip() or "not yet reviewed" for e in err_rows or [])
    table(doc, ["Cause", "Errors"], causes.most_common() or [("no errors file", "")])

    doc.add_heading("6. Cost and reproducibility", 1)
    doc.add_paragraph(
        f"Model {run_log['model']}, prompt {run_log['prompt_version']}, run {run_log['run_at']}. "
        f"{run_log['n_reports']} reports, {run_log['n_flagged']} flagged as invalid output, "
        f"estimated cost ${run_log['estimated_cost_usd']:.2f}. Tokens: "
        + ", ".join(f"{k} {v:,}" for k, v in run_log["tokens"].items()) + ".")

    doc.add_heading("7. Limitations", 1)
    for line in [
        "All reports are synthetic; accuracy on real InGen field reports may be lower.",
        "Gold labels come from one labeller; kappa measures consistency over time, not between people.",
        f"The held-out set has {len(gold)} reports, so rare categories have very few examples and "
        "their per-category numbers are unstable.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    notes = RESULTS / "report_notes.md"   # hand-written findings, one bullet per line
    if notes.exists():
        doc.add_heading("8. Findings and notes", 1)
        for line in notes.read_text(encoding="utf-8").splitlines():
            if line.startswith("- "):
                doc.add_paragraph(line[2:], style="List Bullet")

    out = ROOT / "W02_Evaluation_Report.docx"
    doc.save(out)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
