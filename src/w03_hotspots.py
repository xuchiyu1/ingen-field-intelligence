"""Week 3 task 2: geospatial hotspots, normalised by operating hours.

Unit of analysis: the 25 Rover site-zones (exposure is recorded per site-zone).
For each incident category:
  1. rate per 100 operating hours per zone
  2. each zone vs the rest of the fleet: rate ratio, exact test, Benjamini-Hochberg
  3. Getis-Ord Gi* on the zone rates (distance band 500 m, 999 permutations):
     is a zone and its neighbours together higher than expected by chance?
     With only 25 zones and 1-4 neighbours each, Gi* permutation p-values are
     unstable, so Gi* z is reported as context and the rate test is primary.
Fari is reported at coarse area level only (privacy rule), no hotspot test.

Writes  results/w03/zone_rates.csv, results/w03/hotspots.json, maps/w03_s1_hotspot.png
Usage: python src/w03_hotspots.py
"""

import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from esda.getisord import G_Local
from libpysal.weights import DistanceBand
from statsmodels.stats.multitest import multipletests

from w03_trends import rate_ratio

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/w03"
MAPS = ROOT / "maps"
UTM = "EPSG:32611"          # UTM 11N, metres; covers Los Angeles
BAND_M = 500                # neighbours: zone centres within 500 m
SEQ = ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281"]   # one-hue sequential ramp
INK, HOT = "#1d2433", "#eb6834"


def zone_table(rover, hours):
    pts = gpd.GeoDataFrame(rover, geometry=gpd.points_from_xy(rover.lon, rover.lat),
                           crs="EPSG:4326").to_crs(UTM)
    pts["x"], pts["y"] = pts.geometry.x, pts.geometry.y
    zones = pts.groupby(["site", "zone"])[["x", "y"]].mean()
    zones["hours"] = hours[hours.platform == "Aido Rover"].groupby(["site", "zone"]).operating_hours.sum()
    counts = pd.crosstab([rover.site, rover.zone], rover.pred_category)
    return zones.join(counts).fillna(0)


def weights(zones):
    return DistanceBand(zones[["x", "y"]].values, threshold=BAND_M, binary=True,
                        silence_warnings=True)


def hotspots(zones, categories, seed=42):
    w = weights(zones)
    rows = []
    for cat in categories:
        rate = 100 * zones[cat] / zones.hours
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = G_Local(rate.values, w, star=True, permutations=999, seed=seed)
        for i, (site, zone) in enumerate(zones.index):
            rest = zones.drop(index=(site, zone))
            rr, lo, hi, p = rate_ratio(zones.loc[(site, zone), cat], zones.loc[(site, zone), "hours"],
                                       rest[cat].sum(), rest.hours.sum())
            rows.append({"category": cat, "site": site, "zone": zone,
                         "incidents": int(zones.loc[(site, zone), cat]), "per_100h": rate.iloc[i],
                         "rr_vs_fleet": rr, "ci_low": lo, "ci_high": hi, "p_rate": p,
                         "gi_z": g.Zs[i], "gi_p_sim": g.p_sim[i]})
    t = pd.DataFrame(rows)
    # BH within each category: 25 zone tests per category
    t["q_rate"] = t.groupby("category").p_rate.transform(lambda p: multipletests(p, method="fdr_bh")[1])
    return t


def plot_s1(zones, table):
    s1 = table[table.category == "S1"].set_index(["site", "zone"])
    sites = zones.index.get_level_values(0).unique()
    vmax = s1.per_100h.max()
    fig, axes = plt.subplots(1, len(sites), figsize=(12, 3.0))
    for ax, site in zip(axes, sites):
        z, r = zones.loc[site], s1.loc[site]
        colors = [SEQ[min(int(v / vmax * len(SEQ)), len(SEQ) - 1)] for v in r.per_100h]
        ax.scatter(z.x, z.y, s=520, c=colors, edgecolors="white", linewidths=2, zorder=2)
        for zone, row in r.iterrows():
            hot = row.p_rate < 0.05 and row.rr_vs_fleet > 1
            ax.annotate(f"{zone}\n{row.per_100h:.2f}", (z.loc[zone, "x"], z.loc[zone, "y"]),
                        xytext=(0, -30), textcoords="offset points", ha="center", fontsize=7,
                        color=HOT if hot else INK, fontweight="bold" if hot else "normal")
            if hot:
                ax.scatter(z.loc[zone, "x"], z.loc[zone, "y"], s=760, facecolors="none",
                           edgecolors=HOT, linewidths=2, zorder=3)
        ax.set_title(site, fontsize=9, color=INK)
        ax.set_xticks([]), ax.set_yticks([])
        ax.margins(0.35)
        for s in ax.spines.values():
            s.set_color("#e4e7ec")
    fig.suptitle("S1 navigation incidents per 100 operating hours by patrol zone "
                 "(darker = higher; orange ring = above fleet at unadjusted p < 0.05)",
                 fontsize=9, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(MAPS / "w03_s1_hotspot.png", dpi=160)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(exist_ok=True)
    reports = pd.read_csv(ROOT / "data/classified_corpus.csv")
    hours = pd.read_csv(ROOT / "data/exposure_hours.csv")
    rover = reports[reports.platform == "Aido Rover"]
    cats = sorted(c for c in rover.pred_category.unique() if c != "NO_INCIDENT")

    zones = zone_table(rover, hours)
    table = hotspots(zones, cats)
    table.round(4).to_csv(OUT / "zone_rates.csv", index=False)
    plot_s1(zones, table)

    sig = table[table.p_rate < 0.05].sort_values("p_rate")
    fari = reports[reports.platform == "Fari"]
    fari_h = hours[hours.platform == "Fari"].groupby("site").operating_hours.sum()
    fari_rates = (100 * pd.crosstab(fari.site, fari.pred_category).div(fari_h, axis=0)).round(3)
    summary = {"zones": len(zones), "band_m": BAND_M,
               "significant_after_bh": int((table.q_rate < 0.05).sum()),
               "neighbours_per_zone": {int(k): int(v) for k, v in
                                       pd.Series(weights(zones).cardinalities).value_counts().items()},
               "unadjusted_p05": sig.round(4).to_dict("records"),
               "fari_area_rates_per_100h": fari_rates.to_dict()}
    (OUT / "hotspots.json").write_text(json.dumps(summary, indent=2, default=float))
    print(summary["neighbours_per_zone"])
    print(table.sort_values("q_rate").head(8).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
