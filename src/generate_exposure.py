"""Generate the supplementary exposure and normal-telemetry files for Week 3.

Week 3 compares incident *rates*, not counts, and compares pre-incident
telemetry with normal operation. The corpus has neither, so this script adds
them. It runs after the corpus, does not read or change field_reports.csv or
the sealed answer key, and uses its own seed.

Outputs
  data/exposure_hours.csv     operating hours per site / zone / week
  data/normal_telemetry.csv   one-hour telemetry windows with no incident report

Assumptions (match how generate_corpus.py placed reports)
  - Patrol effort is about equal across Rover site-zones (reports were placed
    uniformly), so hours are drawn around ~16 h/day per site split over its
    5 zones, with ±10% week-to-week noise. Fari areas likewise get equal
    active hours around 10 h/day per area.
  - Normal windows use the generator's no-incident baseline distributions,
    so pre-incident vs normal differences come only from incident behaviour.

Usage: python src/generate_exposure.py [--seed 2026] [--n-normal 3000]
"""

import argparse
import random
from datetime import timedelta

from generate_corpus import (DATA, END, FARI_AREAS, ROVER_SITES, SHARE_FARI, START, ZONES,
                             temperature, write_csv)

ROVER_HOURS_PER_SITE_DAY = 16
FARI_HOURS_PER_AREA_DAY = 10


def exposure(rng):
    rows = []
    week = START - timedelta(days=START.weekday())          # Monday on or before START
    while week <= END:
        days = sum(START <= week + timedelta(days=d) <= END for d in range(7))
        for site in ROVER_SITES:
            for zone in ZONES:
                hours = ROVER_HOURS_PER_SITE_DAY / len(ZONES) * days * rng.gauss(1, 0.1)
                rows.append({"week_start": week.strftime("%Y-%m-%d"), "platform": "Aido Rover",
                             "site": site, "zone": zone, "operating_hours": round(hours, 1)})
        for area in FARI_AREAS:
            hours = FARI_HOURS_PER_AREA_DAY * days * rng.gauss(1, 0.1)
            rows.append({"week_start": week.strftime("%Y-%m-%d"), "platform": "Fari",
                         "site": area, "zone": "", "operating_hours": round(hours, 1)})
        week += timedelta(days=7)
    return rows


def normal_window(rng, ts):
    if rng.random() < SHARE_FARI:
        return {"platform": "Fari", "site": rng.choice(list(FARI_AREAS)), "zone": "",
                "temperature_c": "", "battery_pct": round(rng.uniform(20, 100), 1),
                "battery_drop_pct_1h": "", "motor_current_mean_a": "",
                "motor_current_trend_a_per_h": "", "speed_mean_mps": "",
                "loc_confidence_min": "", "response_latency_s": round(rng.uniform(0.8, 2.0), 2)}
    return {"platform": "Aido Rover", "site": rng.choice(list(ROVER_SITES)),
            "zone": rng.choice(list(ZONES)), "temperature_c": temperature(rng, ts),
            "battery_pct": round(rng.uniform(35, 95), 1),
            "battery_drop_pct_1h": round(rng.uniform(2, 12), 1),
            "motor_current_mean_a": round(rng.gauss(10.0, 1.2), 2),
            "motor_current_trend_a_per_h": round(rng.gauss(0.0, 0.3), 2),
            "speed_mean_mps": round(rng.gauss(1.0, 0.1), 2),
            "loc_confidence_min": round(rng.uniform(0.85, 0.99), 2), "response_latency_s": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n-normal", type=int, default=3000)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    hours = exposure(rng)
    span = int((END - START).total_seconds())
    normal = []
    for i in range(args.n_normal):
        ts = START + timedelta(seconds=rng.randrange(span))
        normal.append({"window_id": f"N{i + 1:05d}", "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                       **normal_window(rng, ts), "is_synthetic": True})
    normal.sort(key=lambda r: r["timestamp"])

    write_csv(DATA / "exposure_hours.csv", hours)
    write_csv(DATA / "normal_telemetry.csv", normal)
    print(f"wrote {len(hours)} exposure rows, {len(normal)} normal telemetry windows")


if __name__ == "__main__":
    main()
