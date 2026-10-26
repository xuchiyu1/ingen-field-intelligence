"""Non-LLM baselines the LLM classifier has to beat.

keyword  hand-written keyword rules derived from the Taxonomy Guide; needs no
         training data, so it runs on any split.
tfidf    TF-IDF + logistic regression trained on the labelled tuning split,
         evaluated on the held-out split.

Outputs results/baseline_<method>_<split>.csv in the same format as
classify_llm.py, so evaluate.py can score both.

Usage
  python src/baseline.py --method keyword --split heldout
  python src/baseline.py --method tfidf            # needs labelled tuning rows
"""

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Checked in order; the first category with a matching pattern wins. Order
# encodes the guide's tie-breaks: designed behaviour and AI misjudgements
# before hardware, faults before their environmental triggers.
KEYWORD_RULES = [
    ("NO_INCIDENT", r"no issues|completed patrol|per safety rule|as configured|working normally|confirmed taken|end of shift"),
    ("S5", r"false alarm|fall alert|bed-exit alert|flagged .* as|intrusion alert|missed a person|classified .* as|not detected|was calm|was fine|still in bed"),
    ("U1", r"kick|vandal|pushed over|blocking .* on purpose|put a cone|teenager"),
    ("H4", r"\bdock(ing)?\b.*(miss|no power|not charging|damaged|misalign|bent)|not charging on its base|missed docking"),
    ("H1", r"\bbatt(ery)?\b|\bbms\b|shut ?down|died|power loss|draining"),
    ("H2", r"hub motor|wheel (locked|not turning|motor)|suspension|pulling to the|grinding"),
    ("H3", r"lens|lidar .*noise|recalibrat|calibration|camera .*cracked|mic array|sensor not reading|face not recognised|cam(era)? .*dirty"),
    ("S3", r"\blte\b|wifi|link timeout|no connection|offline|connection unstable|dropped|stale position|lost conn"),
    ("S4", r"\bapp\b|dashboard|crash|refresh|map view|not showing"),
    ("S1", r"drift|lost|circling|locali[sz]ation|cautious mode|gps|route not completed"),
    ("S2", r"bump|hit|obstacle|plastic bag|curb|would not proceed"),
    ("E1", r"rain|fog|wind|snow|weather|storm"),
    ("E2", r"mud|gravel|sand|slip|flood|wet grass|stuck"),
    ("E3", r"construction|gate|barrier|parked|fencing"),
    ("U2", r"confus|complain|too slow|too long|slowly|waited|accent|quiet|repeat|didn't know|doesn't understand|bored|gives up"),
]


def keyword_predict(text):
    t = text.lower()
    for cat, pattern in KEYWORD_RULES:
        if re.search(pattern, t):
            return cat
    return "NO_INCIDENT"


def load_gold():
    return list(csv.DictReader(open(ROOT / "eval/gold_set.csv", encoding="utf-8")))


def write(rows, preds, name):
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["report_id", "pred_category"])
        w.writeheader()
        for r, p in zip(rows, preds):
            w.writerow({"report_id": r["report_id"], "pred_category": p})
    print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["keyword", "tfidf"], default="keyword")
    ap.add_argument("--split", choices=["tuning", "heldout"], default="heldout")
    args = ap.parse_args()
    gold = load_gold()
    test = [r for r in gold if r["split"] == args.split]

    if args.method == "keyword":
        write(test, [keyword_predict(r["text"]) for r in test],
              f"baseline_keyword_{args.split}")
        return

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    train = [r for r in gold if r["split"] == "tuning" and r["label_category"].strip()]
    if len(train) < 50:
        sys.exit(f"tfidf baseline needs labelled tuning rows; found {len(train)}. "
                 "Label eval/gold_set.csv first.")
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )
    model.fit([r["text"] for r in train], [r["label_category"].strip() for r in train])
    test = [r for r in gold if r["split"] == "heldout"]
    write(test, list(model.predict([r["text"] for r in test])), "baseline_tfidf_heldout")


if __name__ == "__main__":
    main()
