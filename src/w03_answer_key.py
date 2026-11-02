"""Week 3 task 5: open the sealed answer key and check the analysis against it.

Run only after the Week 3 analyses are final. Checks the key's sha256 against
the value published in data/README.md, then reports
  - classifier agreement with generator labels on the full corpus
  - for each planted pattern: what the analysis found and whether it would have
    been found with the true labels (separates classifier error from sample size)

Writes  results/w03/answer_key_check.json
Usage: python src/w03_answer_key.py
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score

from w03_trends import rate_ratio

ROOT = Path(__file__).resolve().parent.parent
KEY = ROOT / "data/sealed/answer_key.csv"
SHA256 = "24e41dccba8d5f6436f881c61fc3c2f815f0c67e797a91ad148d06a7a16777d5"


def zone_rr(rover, hours, label, site="Site_C", zone="North", cat="S1"):
    h = hours[hours.platform == "Aido Rover"].groupby(["site", "zone"]).operating_hours.sum()
    n = rover[rover[label] == cat].groupby(["site", "zone"]).size().reindex(h.index, fill_value=0)
    rr, lo, hi, p = rate_ratio(n[(site, zone)], h[(site, zone)],
                               n.drop((site, zone)).sum(), h.drop((site, zone)).sum())
    rank = int((n / h).rank(ascending=False)[(site, zone)])
    return {"rr": round(rr, 2), "ci": [round(lo, 2), round(hi, 2)], "p": round(p, 4),
            "rank_of_25": rank, "q_bh_25_zones": round(min(1.0, p * 25 / rank), 4) if rank == 1 else None}


def main():
    digest = hashlib.sha256(KEY.read_bytes()).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"answer key changed since sealing: {digest}")
    key = pd.read_csv(KEY)
    reports = pd.read_csv(ROOT / "data/classified_corpus.csv").merge(key, on="report_id")
    hours = pd.read_csv(ROOT / "data/exposure_hours.csv")
    rover = reports[reports.platform == "Aido Rover"]
    w03 = ROOT / "results/w03"
    trends = json.loads((w03 / "trends_summary.json").read_text())
    tele = pd.read_csv(w03 / "telemetry_effects.csv")
    h3 = tele[(tele.category == "H3") & (tele.feature == "motor_current_trend_a_per_h")].iloc[0]

    cold = rover.temperature_c < 0
    true_h1 = rover.true_category == "H1"
    result = {
        "sha256_ok": True,
        "classifier_vs_generator": {
            "category_accuracy": round(accuracy_score(reports.true_category, reports.pred_category), 4),
            "severity_exact": round((reports.pred_severity == reports.severity).mean(), 4),
            "severity_within_1": round(((reports.pred_severity - reports.severity).abs() <= 1).mean(), 4),
            "top_confusions": (reports[reports.true_category != reports.pred_category]
                               .groupby(["true_category", "pred_category"]).size()
                               .sort_values(ascending=False).head(6)
                               .pipe(lambda c: {f"{a}->{b}": int(n) for (a, b), n in c.items()}))},
        "P1_navigation_hotspot": {
            "found_with_predicted_labels": zone_rr(rover, hours, "pred_category"),
            "with_true_labels": zone_rr(rover, hours, "true_category"),
            "verdict": "partial: highest S1 zone in the fleet, but not significant after correction"},
        "P2_cold_battery": {
            "found": trends["cold_battery"],
            "h1_share_true_labels_cold_vs_warm": [round(true_h1[cold].mean(), 3),
                                                  round(true_h1[~cold].mean(), 3)],
            "verdict": "found"},
        "P3_motor_current_before_sensor_faults": {
            "found_trend_diff_a_per_h": round(h3["diff"], 2), "cohens_d": round(h3.cohens_d, 2),
            "verdict": "found"},
        "P4_fari_delay": {"found": {k: trends["fari"][k] for k in
                                    ("delay_rate_ratio_after_vs_before", "ci", "p")},
                          "verdict": "found"},
    }
    (w03 / "answer_key_check.json").write_text(json.dumps(result, indent=2, default=float))
    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
