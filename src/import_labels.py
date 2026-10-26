"""Merge labels exported from eval/label_tool.html into eval/gold_set.csv.

Usage
  python src/import_labels.py ~/Downloads/gold_labels_round1.csv
  python src/import_labels.py ~/Downloads/gold_labels_round2.csv
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval/gold_set.csv"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    incoming = {r["report_id"]: r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))}
    rows = list(csv.DictReader(open(GOLD, encoding="utf-8")))
    fields = list(rows[0])
    updated = 0
    for row in rows:
        new = incoming.get(row["report_id"])
        if not new:
            continue
        for k, v in new.items():
            if k in fields and k != "report_id" and v.strip():
                row[k] = v.strip()
                updated += 1
    with open(GOLD, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    labelled = sum(bool(r["label_category"]) for r in rows)
    round2 = sum(bool(r["round2_category"]) for r in rows)
    print(f"updated {updated} cells; {labelled}/250 labelled, {round2}/50 round-2 labels")


if __name__ == "__main__":
    main()
