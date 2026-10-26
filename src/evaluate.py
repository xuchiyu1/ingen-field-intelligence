"""Score predictions against the hand-labelled gold set.

Reports overall accuracy, per-category precision / recall / F1, a confusion
matrix, severity agreement (when predicted), and Cohen's kappa between the
two human labelling rounds. Only rows with a gold label are scored.

Usage
  python src/evaluate.py results/llm_classify_v1_gold_set_heldout.csv
  python src/evaluate.py results/baseline_keyword_heldout.csv --split heldout
  python src/evaluate.py --agreement          # human round 1 vs round 2
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from sklearn.metrics import (accuracy_score, classification_report,
                             cohen_kappa_score, confusion_matrix)

ROOT = Path(__file__).resolve().parent.parent


def load_gold(split=None):
    rows = list(csv.DictReader(open(ROOT / "eval/gold_set.csv", encoding="utf-8")))
    rows = [r for r in rows if r["label_category"].strip()]
    if split:
        rows = [r for r in rows if r["split"] == split]
    return {r["report_id"]: r for r in rows}


def agreement():
    gold = load_gold()
    pairs = [(r["label_category"].strip(), r["round2_category"].strip())
             for r in gold.values() if r["round2_category"].strip()]
    if len(pairs) < 10:
        sys.exit(f"need round-2 labels on the double-label rows; found {len(pairs)}")
    a, b = zip(*pairs)
    # Per-category kappa (one-vs-rest): below 0.6 means the rule needs fixing.
    per_cat = {}
    for c in sorted(set(a) | set(b)):
        x = [v == c for v in a]
        y = [v == c for v in b]
        if any(x) or any(y):
            per_cat[c] = round(cohen_kappa_score(x, y), 3) if len(set(x + y)) > 1 else 1.0
    sev = [(r["label_severity"].strip(), r["round2_severity"].strip())
           for r in gold.values() if r["round2_severity"].strip() and r["label_severity"].strip()]
    print(json.dumps({
        "n": len(pairs),
        "cohen_kappa": round(cohen_kappa_score(a, b), 3),
        "raw_agreement": round(sum(x == y for x, y in pairs) / len(pairs), 3),
        "per_category_kappa": per_cat,
        "categories_below_0.6": [c for c, k in per_cat.items() if k < 0.6],
        "severity_kappa": round(cohen_kappa_score(*zip(*sev)), 3) if len(sev) >= 10 else None,
        "disagreement_pairs": sorted({(x, y) for x, y in pairs if x != y}),
    }, indent=2))


def score(pred_path, split):
    gold = load_gold(split)
    if not gold:
        sys.exit("no labelled gold rows to score against; label eval/gold_set.csv first")
    preds = {r["report_id"]: r for r in csv.DictReader(open(pred_path, encoding="utf-8"))}
    ids = [i for i in gold if i in preds]
    flagged = [i for i in ids if not preds[i]["pred_category"]]
    ids = [i for i in ids if preds[i]["pred_category"]]
    y_true = [gold[i]["label_category"].strip() for i in ids]
    y_pred = [preds[i]["pred_category"] for i in ids]
    labels = sorted(set(y_true) | set(y_pred))

    print(f"{pred_path}: {len(ids)} scored, {len(flagged)} flagged (no valid output)")
    print(f"accuracy: {accuracy_score(y_true, y_pred):.3f}\n")
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))

    print("confusion matrix (rows = gold, columns = predicted)")
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    print("      " + " ".join(f"{l[:5]:>5}" for l in labels))
    for l, row in zip(labels, cm):
        print(f"{l[:5]:>5} " + " ".join(f"{v:>5}" for v in row))

    sev = [(gold[i]["label_severity"].strip(), str(preds[i].get("pred_severity", "")))
           for i in ids if gold[i]["label_severity"].strip() and preds[i].get("pred_severity")]
    if sev:
        exact = sum(a == b for a, b in sev) / len(sev)
        within1 = sum(abs(int(a) - int(b)) <= 1 for a, b in sev) / len(sev)
        print(f"\nseverity: exact {exact:.3f}, within one level {within1:.3f} (n={len(sev)})")

    conf = [(preds[i].get("confidence", ""), gold[i]["label_category"].strip() == preds[i]["pred_category"])
            for i in ids if preds[i].get("confidence")]
    if conf:
        # Human-review threshold: does accuracy drop in the low-confidence band?
        print("\naccuracy by confidence band (human-review threshold)")
        for band in ("high", "medium", "low"):
            hits = [ok for c, ok in conf if c == band]
            if hits:
                print(f"  {band:>6}: {sum(hits) / len(hits):.3f} on {len(hits)} reports "
                      f"({len(hits) / len(conf):.0%} of outputs)")

    errors = [(i, gold[i]["label_category"].strip(), preds[i]["pred_category"])
              for i in ids if gold[i]["label_category"].strip() != preds[i]["pred_category"]]
    out = Path(pred_path).with_name(Path(pred_path).stem + "_errors.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["report_id", "gold", "pred", "text", "error_cause"])
        for i, g, p in errors:
            w.writerow([i, g, p, gold[i]["text"], ""])
    print(f"\n{len(errors)} errors written to {out.relative_to(ROOT)} "
          "(fill error_cause: rule unclear / genuinely ambiguous / multiple issues / model misreading / gold label wrong)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", nargs="?")
    ap.add_argument("--split", choices=["tuning", "heldout"])
    ap.add_argument("--agreement", action="store_true")
    args = ap.parse_args()
    if args.agreement:
        agreement()
    elif args.predictions:
        score(ROOT / args.predictions if not Path(args.predictions).is_absolute()
              else Path(args.predictions), args.split)
    else:
        ap.error("give a predictions file or --agreement")


if __name__ == "__main__":
    main()
