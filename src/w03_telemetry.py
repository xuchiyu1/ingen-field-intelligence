"""Week 3 task 3: does telemetry in the hour before an incident differ from normal operation?

Compares each Rover incident category's pre-incident telemetry with the
no-incident windows in data/normal_telemetry.csv: mean difference with a 95%
Welch CI and Cohen's d, Benjamini-Hochberg across all category x feature tests.
Then a cross-validated logistic regression (5-fold, stratified) tests how well
telemetry alone separates pre-incident hours from normal hours, overall and per
category. Fari: response latency before U2 complaints vs normal.

Writes  results/w03/telemetry_effects.csv, results/w03/telemetry_cv.csv,
        results/w03/telemetry_summary.json, figures/w03_motor_current.png
Usage: python src/w03_telemetry.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/w03"
FIG = ROOT / "figures"
FEATURES = ["battery_pct", "battery_drop_pct_1h", "motor_current_mean_a",
            "motor_current_trend_a_per_h", "speed_mean_mps", "loc_confidence_min"]
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#1d2433", "#667085"


def effects(rover, normal):
    rows = []
    for cat, g in rover.groupby("pred_category"):
        for f in FEATURES:
            a, b = g[f].dropna(), normal[f].dropna()
            t = stats.ttest_ind(a, b, equal_var=False)
            ci = t.confidence_interval()
            pooled = np.sqrt((a.var() + b.var()) / 2)
            rows.append({"category": cat, "feature": f, "n": len(a),
                         "incident_mean": a.mean(), "normal_mean": b.mean(),
                         "diff": a.mean() - b.mean(), "ci_low": ci.low, "ci_high": ci.high,
                         "cohens_d": (a.mean() - b.mean()) / pooled, "p": t.pvalue})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p, method="fdr_bh")[1]
    return t


def cv_auc(pos, normal, seed=42):
    X = pd.concat([pos[FEATURES], normal[FEATURES]])
    y = np.r_[np.ones(len(pos)), np.zeros(len(normal))]
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
    folds = StratifiedKFold(5, shuffle=True, random_state=seed)
    auc = cross_val_score(model, X, y, cv=folds, scoring="roc_auc")
    coef = model.fit(X, y)[-1].coef_[0]
    top = FEATURES[int(np.argmax(np.abs(coef)))]
    return auc.mean(), auc.std(), top


def plot_h3(rover, normal):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2))
    h3 = rover[rover.pred_category == "H3"]
    other = rover[~rover.pred_category.isin(["H3", "NO_INCIDENT"])]
    for ax, f, title in zip(axes, ["motor_current_mean_a", "motor_current_trend_a_per_h"],
                            ["Motor current, mean (A)", "Motor current trend (A per hour)"]):
        bins = np.linspace(min(normal[f].min(), h3[f].min()), max(normal[f].max(), h3[f].max()), 40)
        for d, color, label in ((normal, BLUE, "normal hours"), (other, MUTED, "other incidents"),
                                (h3, ORANGE, "before H3 sensor fault")):
            ax.hist(d[f], bins=bins, density=True, histtype="step", linewidth=2, color=color, label=label)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_yticks([])
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "w03_motor_current.png", dpi=160)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(exist_ok=True)
    reports = pd.read_csv(ROOT / "data/classified_corpus.csv")
    normal_all = pd.read_csv(ROOT / "data/normal_telemetry.csv")
    rover = reports[reports.platform == "Aido Rover"]
    normal = normal_all[normal_all.platform == "Aido Rover"]

    eff = effects(rover, normal)
    eff.round(4).to_csv(OUT / "telemetry_effects.csv", index=False)

    incidents = rover[rover.pred_category != "NO_INCIDENT"]
    cv_rows = [("any incident", len(incidents), *cv_auc(incidents, normal))]
    for cat, g in incidents.groupby("pred_category"):
        cv_rows.append((cat, len(g), *cv_auc(g, normal)))
    cv = pd.DataFrame(cv_rows, columns=["target", "n_incident", "auc_mean", "auc_sd", "top_feature"])
    cv.round(3).to_csv(OUT / "telemetry_cv.csv", index=False)
    plot_h3(rover, normal)

    fari = reports[reports.platform == "Fari"]
    fari_normal = normal_all[normal_all.platform == "Fari"].response_latency_s
    u2 = fari[fari.pred_category == "U2"].response_latency_s
    t = stats.ttest_ind(u2, fari_normal, equal_var=False)
    strong = eff[(eff.q_bh < 0.05) & (eff.cohens_d.abs() >= 0.8)]
    summary = {"normal_windows": len(normal), "incident_windows": len(incidents),
               "large_effects_q05_d08": strong[["category", "feature", "diff", "ci_low", "ci_high",
                                                "cohens_d"]].round(3).to_dict("records"),
               "cv_auc": cv.round(3).to_dict("records"),
               "fari_u2_latency_s": round(u2.mean(), 2), "fari_normal_latency_s": round(fari_normal.mean(), 2),
               "fari_latency_diff_ci": [round(t.confidence_interval().low, 2),
                                        round(t.confidence_interval().high, 2)]}
    (OUT / "telemetry_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(strong.round(2).to_string(index=False))
    print(cv.round(3).to_string(index=False))
    print({k: v for k, v in summary.items() if k.startswith("fari")})


if __name__ == "__main__":
    main()
