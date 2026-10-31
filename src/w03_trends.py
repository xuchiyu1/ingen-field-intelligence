"""Week 3 task 1 and 4: incident rates, trends, severity and Fari feedback themes.

Every comparison uses incidents per 100 operating hours (data/exposure_hours.csv),
not raw counts, and comes with a confidence interval or a test. Tests across many
categories or sites are corrected with Benjamini-Hochberg (false discovery rate).

Reads   data/classified_corpus.csv, data/exposure_hours.csv, data/normal_telemetry.csv
Writes  results/w03/*.csv, results/w03/trends_summary.json, figures/w03_*.png

Usage: python src/w03_trends.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/w03"
FIG = ROOT / "figures"
FARI_UPDATE = pd.Timestamp("2026-04-01")
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#1d2433", "#667085"

# Fari complaint themes: regex on lower-case text (typo-tolerant where cheap)
THEMES = {
    "response delay": r"wait|too long|slow|pause|ages",
    "voice too quiet": r"quiet|volume",
    "screen confusing": r"screen|confus",
    "repetitive conversation": r"repeat|same joke",
    "accent not understood": r"accent",
}


def load():
    reports = pd.read_csv(ROOT / "data/classified_corpus.csv", parse_dates=["timestamp"])
    reports["week_start"] = (reports.timestamp.dt.normalize()
                             - pd.to_timedelta(reports.timestamp.dt.weekday, unit="D"))
    hours = pd.read_csv(ROOT / "data/exposure_hours.csv", parse_dates=["week_start"])
    return reports, hours


def rate_ratio(a, ha, b, hb):
    """Rate ratio of a/ha vs b/hb with a 95% CI and an exact conditional test."""
    rr = (a / ha) / (b / hb)
    se = np.sqrt(1 / a + 1 / b) if a and b else np.nan
    lo, hi = rr * np.exp(-1.96 * se), rr * np.exp(1.96 * se)
    p = stats.binomtest(int(a), int(a + b), ha / (ha + hb)).pvalue
    return rr, lo, hi, p


def weekly_trends(rover, hours):
    """Quasi-Poisson regression per category: weekly count ~ week, offset log(hours)."""
    exp_week = hours[hours.platform == "Aido Rover"].groupby("week_start").operating_hours.sum()
    week_idx = pd.Series(np.arange(len(exp_week)), index=exp_week.index)
    rows = []
    for cat, g in rover.groupby("pred_category"):
        y = g.groupby("week_start").size().reindex(exp_week.index, fill_value=0)
        X = sm.add_constant(week_idx.values)
        fit = sm.GLM(y.values, X, family=sm.families.Poisson(),
                     offset=np.log(exp_week.values)).fit(scale="X2")
        b, se = fit.params[1], fit.bse[1]
        rows.append({"category": cat, "incidents": int(y.sum()),
                     "per_100h": 100 * y.sum() / exp_week.sum(),
                     "rr_per_4_weeks": np.exp(4 * b),
                     "ci_low": np.exp(4 * (b - 1.96 * se)), "ci_high": np.exp(4 * (b + 1.96 * se)),
                     "p": fit.pvalues[1]})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p, method="fdr_bh")[1]
    return t.sort_values("per_100h", ascending=False), exp_week


def site_rates(rover, hours):
    """Each site vs the rest of the fleet, per category."""
    h = hours[hours.platform == "Aido Rover"].groupby("site").operating_hours.sum()
    rows = []
    for cat, g in rover.groupby("pred_category"):
        n = g.groupby("site").size().reindex(h.index, fill_value=0)
        for site in h.index:
            rr, lo, hi, p = rate_ratio(n[site], h[site], n.drop(site).sum(), h.drop(site).sum())
            rows.append({"category": cat, "site": site, "incidents": int(n[site]),
                         "per_100h": 100 * n[site] / h[site], "rr_vs_rest": rr,
                         "ci_low": lo, "ci_high": hi, "p": p})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p, method="fdr_bh")[1]
    return t.sort_values("q_bh")


def cold_battery(rover):
    """H1 rate below vs at/above 0 °C. Hours by temperature are estimated from the
    share of normal-operation windows below 0 °C (windows are sampled uniformly in time)."""
    normal = pd.read_csv(ROOT / "data/normal_telemetry.csv")
    normal = normal[normal.platform == "Aido Rover"]
    p_cold = (normal.temperature_c < 0).mean()
    cold = rover.temperature_c < 0
    h1 = rover.pred_category == "H1"
    a, b = int((h1 & cold).sum()), int((h1 & ~cold).sum())
    share_cold = h1[cold].mean(), h1[~cold].mean()
    _, fisher_p = stats.fisher_exact([[a, int(cold.sum()) - a], [b, int((~cold).sum()) - b]])
    rr, lo, hi, p = rate_ratio(a, p_cold, b, 1 - p_cold)   # hours cancel; only the split matters
    return {"share_of_time_below_0c": round(p_cold, 3), "h1_reports_cold": a, "h1_reports_warm": b,
            "h1_share_of_reports_cold": round(share_cold[0], 3),
            "h1_share_of_reports_warm": round(share_cold[1], 3), "fisher_p_share": fisher_p,
            "h1_rate_ratio_cold_vs_warm": round(rr, 2), "ci": [round(lo, 2), round(hi, 2)], "p": p}


def severity(reports):
    rows = []
    for (plat, cat), g in reports.groupby(["platform", "pred_category"]):
        k, n = int((g.pred_severity >= 3).sum()), len(g)
        lo, hi = proportion_confint(k, n, method="wilson")
        rows.append({"platform": plat, "category": cat, "reports": n,
                     "share_sev_3_4": k / n, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows).sort_values("share_sev_3_4", ascending=False)


def fari_themes(fari, hours):
    """Theme shares of Fari U2 complaints and the delay theme before vs after the update."""
    u2 = fari[fari.pred_category == "U2"].copy()
    text = u2.text.str.lower()
    for name, rx in THEMES.items():
        u2[name] = text.str.contains(rx)
    u2["other"] = ~u2[list(THEMES)].any(axis=1)
    u2["after_update"] = u2.timestamp >= FARI_UPDATE
    share = u2.groupby("after_update")[list(THEMES) + ["other"]].mean().T
    share.columns = ["before_apr1", "after_apr1"]

    # exposure before / after: spread each week's hours evenly over its days
    fh = hours[hours.platform == "Fari"].groupby("week_start").operating_hours.sum()
    days = pd.concat([pd.Series(v / 7, index=pd.date_range(w, periods=7)) for w, v in fh.items()])
    h_after, h_before = days[days.index >= FARI_UPDATE].sum(), days[days.index < FARI_UPDATE].sum()
    delay = u2[u2["response delay"]]
    a, b = int(delay.after_update.sum()), int((~delay.after_update).sum())
    rr, lo, hi, p = rate_ratio(a, h_after, b, h_before)
    lat = fari.assign(after=fari.timestamp >= FARI_UPDATE).groupby("after").response_latency_s
    quotes = {t: u2[u2[t]].text.iloc[0] for t in THEMES}
    return share, {
        "u2_reports": len(u2), "delay_before": b, "delay_after": a,
        "delay_per_100h_before": round(100 * b / h_before, 3),
        "delay_per_100h_after": round(100 * a / h_after, 3),
        "delay_rate_ratio_after_vs_before": round(rr, 2), "ci": [round(lo, 2), round(hi, 2)], "p": p,
        "mean_latency_s_before": round(lat.mean()[False], 2),
        "mean_latency_s_after": round(lat.mean()[True], 2),
        "example_quotes": quotes}


def plot_weekly(rover, exp_week, fari, hours):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.grid(axis="y", color="#e4e7ec", linewidth=0.8)
        ax.set_axisbelow(True)
    for cat, color in (("H1", BLUE), ("S1", ORANGE)):
        y = rover[rover.pred_category == cat].groupby("week_start").size().reindex(exp_week.index,
                                                                                   fill_value=0)
        axes[0].plot(exp_week.index, 100 * y / exp_week, color=color, linewidth=2, label=cat)
        axes[0].annotate(cat, (exp_week.index[-1], 100 * y.iloc[-1] / exp_week.iloc[-1]),
                         xytext=(4, 0), textcoords="offset points", color=INK, fontsize=8)
    axes[0].set_title("Rover H1 battery vs S1 navigation, incidents per 100 h", fontsize=9,
                      color=INK, loc="left")
    axes[0].legend(frameon=False, fontsize=8)

    fh = hours[hours.platform == "Fari"].groupby("week_start").operating_hours.sum()
    u2 = fari[(fari.pred_category == "U2") & fari.text.str.lower().str.contains(THEMES["response delay"])]
    y = u2.groupby("week_start").size().reindex(fh.index, fill_value=0)
    axes[1].plot(fh.index, 100 * y / fh, color=BLUE, linewidth=2)
    axes[1].axvline(FARI_UPDATE, color=MUTED, linestyle="--", linewidth=1)
    axes[1].annotate("Apr 1 update", (FARI_UPDATE, axes[1].get_ylim()[1] * 0.92), xytext=(4, 0),
                     textcoords="offset points", color=MUTED, fontsize=8)
    axes[1].set_title("Fari response-delay complaints per 100 active h", fontsize=9,
                      color=INK, loc="left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "w03_weekly_rates.png", dpi=160)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(exist_ok=True)
    reports, hours = load()
    rover = reports[reports.platform == "Aido Rover"]
    fari = reports[reports.platform == "Fari"]

    trends, exp_week = weekly_trends(rover, hours)
    sites = site_rates(rover, hours)
    sev = severity(reports)
    theme_share, fari_summary = fari_themes(fari, hours)
    cold = cold_battery(rover)
    for name, df in (("rover_category_trends", trends), ("rover_site_rates", sites),
                     ("severity_by_category", sev), ("fari_u2_themes", theme_share)):
        df.round(4).to_csv(OUT / f"{name}.csv", index=name == "fari_u2_themes")
    plot_weekly(rover, exp_week, fari, hours)

    summary = {"rover_hours": round(exp_week.sum()), "cold_battery": cold, "fari": fari_summary,
               "significant_trends_q05": trends[trends.q_bh < 0.05].category.tolist(),
               "significant_site_cells_q05": sites[sites.q_bh < 0.05][
                   ["category", "site", "rr_vs_rest", "q_bh"]].round(4).to_dict("records")}
    (OUT / "trends_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(trends.round(3).to_string(index=False))
    print(theme_share.round(2))
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
