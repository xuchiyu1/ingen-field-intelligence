"""Draw the 250-report gold set for hand-labelling and split it.

Writes eval/gold_set.csv with empty label columns. Labels must be filled in
from W01_Taxonomy_Guide.docx only, never from data/sealed/answer_key.csv.
50 reports are marked for a second labelling round (Cohen's kappa).

Usage: python src/sample_gold_set.py [--seed 7]
"""

import argparse
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N_ROVER, N_FARI, N_TUNING, N_DOUBLE = 200, 50, 150, 50


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    rows = list(csv.DictReader(open(ROOT / "data/field_reports.csv", encoding="utf-8")))
    rover = [r for r in rows if r["platform"] == "Aido Rover"]
    fari = [r for r in rows if r["platform"] == "Fari"]
    gold = rng.sample(rover, N_ROVER) + rng.sample(fari, N_FARI)
    rng.shuffle(gold)

    out = []
    for i, r in enumerate(gold):
        out.append({
            "report_id": r["report_id"], "platform": r["platform"], "text": r["text"],
            "split": "tuning" if i < N_TUNING else "heldout",
            "double_label": "yes" if i % 5 == 0 else "",  # every 5th report → 50 total
            "label_category": "", "label_severity": "", "label_root_cause_stated": "",
            "borderline": "", "notes": "",
            "round2_category": "", "round2_severity": "",
        })
    (ROOT / "eval").mkdir(exist_ok=True)
    with open(ROOT / "eval/gold_set.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} reports: "
          f"{sum(o['split'] == 'tuning' for o in out)} tuning, "
          f"{sum(o['split'] == 'heldout' for o in out)} held-out, "
          f"{sum(o['double_label'] == 'yes' for o in out)} double-label")


if __name__ == "__main__":
    main()
