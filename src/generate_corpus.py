"""Generate a synthetic corpus of robot field reports with planted patterns.

Outputs
  data/field_reports.csv         reports + metadata + telemetry (no labels)
  data/sealed/answer_key.csv     generator labels and planted-pattern flags
  data/sealed/planted_patterns.md

The answer key is sealed: it must not be opened before Week 3, and the gold
set is labelled from the Taxonomy Guide, not from these labels.

Usage: python src/generate_corpus.py [--n 2000] [--seed 42]
"""

import argparse
import csv
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEALED = DATA / "sealed"

START = datetime(2026, 1, 1)
END = datetime(2026, 6, 30)
FARI_UPDATE = datetime(2026, 4, 1)  # planted pattern P4 starts after this date
SHARE_FARI = 0.2

# ---------------------------------------------------------------------------
# Sites. Rover sites have patrol zones; Fari areas are coarse (privacy rule).
# ---------------------------------------------------------------------------
ROVER_SITES = {
    "Site_A": (34.0522, -118.2437),
    "Site_B": (33.9416, -118.4085),
    "Site_C": (34.1478, -118.1445),
    "Site_D": (33.8366, -117.9143),
    "Site_E": (34.2805, -118.7390),
}
ZONES = {"North": (0.004, 0.0), "South": (-0.004, 0.0), "East": (0.0, 0.005),
         "West": (0.0, -0.005), "Dock": (0.0, 0.0)}
FARI_AREAS = {"Area_1": (34.05, -118.25), "Area_2": (34.15, -118.14),
              "Area_3": (33.84, -117.91)}

# Mean temperature (°C) by month for the deployment region; nights are colder.
MONTH_TEMP = {1: 1, 2: 3, 3: 7, 4: 11, 5: 15, 6: 19}

# ---------------------------------------------------------------------------
# Category mix per platform (weights, normalised at sampling time).
# Codes follow W01_Taxonomy_Guide.docx.
# ---------------------------------------------------------------------------
ROVER_MIX = {"H1": 12, "H2": 7, "H3": 8, "H4": 6, "S1": 11, "S2": 8, "S3": 8,
             "S4": 4, "S5": 6, "E1": 8, "E2": 7, "E3": 5, "U1": 4, "U2": 2,
             "NO_INCIDENT": 4}
FARI_MIX = {"U2": 35, "S5": 20, "S4": 14, "S3": 8, "H3": 7, "H1": 5, "H4": 4,
            "NO_INCIDENT": 7}

SEVERITY = {  # weights for severity 1..4
    "H1": [2, 4, 3, 1], "H2": [1, 3, 4, 2], "H3": [2, 4, 3, 1], "H4": [2, 4, 3, 1],
    "S1": [2, 5, 2, 1], "S2": [2, 4, 3, 1], "S3": [3, 4, 2, 1], "S4": [5, 4, 1, 0],
    "S5": [3, 4, 2, 1], "E1": [3, 5, 2, 0], "E2": [2, 4, 4, 0], "E3": [4, 4, 2, 0],
    "U1": [1, 3, 3, 3], "U2": [4, 5, 1, 0], "NO_INCIDENT": [1, 0, 0, 0],
}

ROVER_AUTHORS = {"operator": 5, "technician": 3, "guard": 2}
FARI_AUTHORS = {"care_staff": 6, "family": 3, "resident_via_staff": 1}

# ---------------------------------------------------------------------------
# Text templates. {u}=unit, {z}=zone, {n}=number, {m}=minutes.
# A template ending in " | cause" states the root cause.
# ---------------------------------------------------------------------------
ROVER_T = {
    "H1": ["Unit {u} battery dropped from {n}% to {n2}% in {m} min on normal route.",
           "BMS cell imbalance warning on unit {u}, rover went to safe stop near {z}.",
           "Rover {u} shut down unexpectedly in {z} zone, battery showed {n}% before.",
           "Unit {u} died near the {z} gate overnight, it was freezing | cause",
           "Battery draining much faster than usual on {u}, had to return early."],
    "H2": ["Rear-left hub motor overcurrent fault on unit {u}, wheel locked.",
           "Grinding noise from front suspension on {u} after patrol.",
           "Unit {u} pulling to the right, possible wheel motor issue.",
           "Right drive wheel not turning on {u}, technician called."],
    "H3": ["PTZ camera lens fogged on unit {u}, footage unusable in {z}.",
           "LiDAR on {u} returning noise on right side, needs recalibration.",
           "Thermal camera on unit {u} reading way off, needs calibration.",
           "Front camera on {u} cracked, image blurry | cause",
           "Mic array on unit {u} not picking up sound, check hardware."],
    "H4": ["Unit {u} missed docking {k} times, contacts look misaligned.",
           "Dock at {z} shows no power, rover sat at {n}% all night.",
           "Rover {u} reached dock but not charging.",
           "Charging dock at {z} damaged, connector bent."],
    "S1": ["Unit {u} drifted off patrol path near {z}, recovered after GPS re-lock.",
           "Rover {u} kept circling in {z}, route not completed.",
           "Localisation confidence low on {u} in {z} zone for {m} min.",
           "Unit {u} went into cautious mode in {z}, position jumping on map.",
           "Rover {u} got lost between buildings in {z}, GPS weak there | cause"],
    "S2": ["Unit {u} bumped into a parked cart in {z}.",
           "Rover {u} stopped {m} min for a plastic bag, would not proceed.",
           "Unit {u} did not see a low curb in {z} and hit it.",
           "False obstacle stop on {u} in {z}, nothing there."],
    "S3": ["Lost LTE on unit {u} for {m} min in {z}, video feed dropped.",
           "Dashboard showing stale position for {u}, link timeout.",
           "WiFi dropouts on {u} near {z}, telemetry delayed.",
           "No connection to unit {u} for {m} min, came back on its own."],
    "S4": ["Alert list on dashboard doesn't refresh until page reload.",
           "Ops app crashed when opening unit {u} video.",
           "Map view on dashboard freezes when zooming into {z}.",
           "Mobile app shows wrong battery level for {u}."],
    "S5": ["Unit {u} flagged a fox as an intruder in {z} twice tonight.",
           "Rover {u} raised intrusion alert for a swaying tree branch.",
           "Unit {u} missed a person walking through {z}, seen on CCTV.",
           "Rover {u} classified a staff member as unknown person again."],
    "E1": ["Heavy rain, unit {u} paused patrol per weather rule.",
           "Fog in {z}, camera range reduced on {u}, continued on LiDAR.",
           "Strong wind, rover {u} slowed down and alerts were noisy.",
           "Unit {u} stopped patrol due to heavy rain in {z} | cause"],
    "E2": ["Unit {u} stuck in mud by the {z} fence.",
           "Rover {u} slowed to 0.5 m/s on loose gravel, patrol late.",
           "Unit {u} wheels slipping on wet grass in {z}, made it through slowly.",
           "Flooded path in {z}, rover {u} could not pass."],
    "E3": ["Construction fencing across route in {z}, unit {u} rerouted.",
           "Truck parked over the dock path at {z}, {u} could not reach dock.",
           "Gate in {z} locked, rover {u} waited {m} min.",
           "Barrier closed at {z} entrance, unit {u} patrol incomplete."],
    "U1": ["Teenagers kicked unit {u} in {z}, camera housing cracked.",
           "Someone put a cone on top of the LiDAR on {u}.",
           "People blocking rover {u} on purpose in {z} for {m} min.",
           "Unit {u} pushed over by a visitor in {z} | cause"],
    "U2": ["Guard didn't know how to acknowledge the alert from {u}.",
           "Operator confused by cautious mode message on unit {u}.",
           "Site manager complained rover {u} is too slow in {z}."],
    "NO_INCIDENT": ["Unit {u} completed patrol of {z}, no issues.",
                    "Rover {u} returned to dock at end of shift, battery {n}%.",
                    "Gas detected near {z}, unit {u} stopped per safety rule and resumed after clear.",
                    "Night patrol on {u}, reduced speed as configured."],
}

FARI_T = {
    "U2_delay": ["Fari takes too long to answer, my mother gives up.",
                 "Long pause before Fari replies, residents lose interest.",
                 "Fari responds very slowly since last week.",
                 "Resident asked Fari a question and waited ages for a reply."],
    "U2_other": ["Fari doesn't understand one resident's accent.",
                 "Resident says Fari's voice is too quiet even at max.",
                 "My father finds Fari's screen confusing.",
                 "Fari keeps repeating the same joke, residents bored."],
    "S5": ["Fari raised a fall alert, resident was only bending to pick up a cup.",
           "Fari said resident was calm but she was clearly in pain.",
           "Fari heart-rate reading {n} BPM, resident was fine.",
           "Fall not detected by Fari, staff found resident on the floor | cause",
           "Night bed-exit alert from Fari, resident still in bed."],
    "S4": ["Family app crashes when opening video call.",
           "Caregiver dashboard not refreshing resident cards.",
           "Medication schedule not showing in the app."],
    "S3": ["Fari offline for {m} min, no WiFi in the room.",
           "Video call to Fari dropped twice, connection unstable."],
    "H3": ["Fari camera lens dirty, face not recognised.",
           "Fari SpO2 sensor not reading, touch surface faulty."],
    "H1": ["Fari shut down in the afternoon, battery not holding charge.",
           "Fari battery low warning even after full charge."],
    "H4": ["Fari not charging on its base, contacts loose."],
    "NO_INCIDENT": ["Fari reminded resident about medication, confirmed taken.",
                    "Weekly check, Fari working normally."],
}

SECONDARY_T = {  # appended when a report mixes two issues
    "H1": "battery also low.", "S3": "lost connection briefly too.",
    "H3": "camera also dirty.", "S1": "also drifted off route earlier.",
    "E1": "it was raining.", "S4": "app was slow as well.",
}

ABBREV = [("battery", "batt"), ("navigation", "nav"), ("minutes", "mins"),
          ("approximately", "approx"), ("camera", "cam"), ("technician", "tech"),
          ("dashboard", "dash"), ("connection", "conn"), ("unit", "u"),
          ("because", "bc"), ("before", "b4")]


# ---------------------------------------------------------------------------
def pick(rng, weights):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def temperature(rng, ts):
    night = ts.hour < 6 or ts.hour >= 21
    return round(rng.gauss(MONTH_TEMP[ts.month] - (4 if night else 0), 4), 1)


def add_noise(rng, text):
    """Make text look hand-written: shorthand, typos, casing, punctuation."""
    if rng.random() < 0.4:
        for full, short in ABBREV:
            if full in text.lower() and rng.random() < 0.6:
                text = text.replace(full, short).replace(full.capitalize(), short)
    if rng.random() < 0.25:  # swap two letters inside one word
        words = text.split()
        i = rng.randrange(len(words))
        w = words[i]
        if len(w) > 4:
            j = rng.randrange(1, len(w) - 2)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
        text = " ".join(words)
    if rng.random() < 0.2:
        text = text.lower()
    if rng.random() < 0.2:
        text = text.rstrip(".")
    if rng.random() < 0.1:
        text += rng.choice([" pls check", " FYI", " - logged", " ticket raised"])
    return text


def fill(rng, template):
    n = rng.randint(30, 80)
    return template.format(
        u=f"R{rng.randint(1, 12):02d}", z=rng.choice(list(ZONES)), n=n,
        n2=max(3, n - rng.randint(20, 45)), m=rng.randint(5, 90),
        k=rng.randint(2, 4), x=rng.choice(["A", "B", "C", "D"]))


def rover_report(rng, ts):
    site = rng.choice(list(ROVER_SITES))
    zone = rng.choice(list(ZONES))
    temp = temperature(rng, ts)
    mix = dict(ROVER_MIX)
    pattern = ""
    if site == "Site_C" and zone == "North":   # P1: navigation hotspot
        mix["S1"] *= 3
    if temp < 0:                               # P2: cold-weather battery issues
        mix["H1"] *= 2
    cat = pick(rng, mix)
    if cat == "S1" and site == "Site_C" and zone == "North":
        pattern = "P1"
    elif cat == "H1" and temp < 0:
        pattern = "P2"

    template = rng.choice(ROVER_T[cat])
    cause_stated = template.endswith("| cause")
    text = fill(rng, template.replace(" | cause", "")).replace("the North", "the north")

    # Telemetry for the hour before the report.
    battery = rng.uniform(35, 95)
    drop = rng.uniform(2, 12)
    current = rng.gauss(10.0, 1.2)
    trend = rng.gauss(0.0, 0.3)
    speed = rng.gauss(1.0, 0.1)
    loc_conf = rng.uniform(0.85, 0.99)
    if cat == "H1":
        battery, drop = rng.uniform(5, 30), rng.uniform(15, 40)
    if cat == "H3":                            # P3: rising motor current before sensor faults
        current *= rng.uniform(1.2, 1.3)
        trend = rng.uniform(0.8, 1.8)
        pattern = "P3"
    if cat == "S1":
        loc_conf = rng.uniform(0.3, 0.65)
    if cat in ("E1", "E2"):
        speed = rng.uniform(0.4, 0.8)

    lat0, lon0 = ROVER_SITES[site]
    dlat, dlon = ZONES[zone]
    return {
        "platform": "Aido Rover", "site": site, "zone": zone,
        "lat": round(lat0 + dlat + rng.gauss(0, 0.0008), 6),
        "lon": round(lon0 + dlon + rng.gauss(0, 0.0008), 6),
        "temperature_c": temp, "author_role": pick(rng, ROVER_AUTHORS), "text": text,
        "battery_pct": round(battery, 1), "battery_drop_pct_1h": round(drop, 1),
        "motor_current_mean_a": round(current, 2),
        "motor_current_trend_a_per_h": round(trend, 2),
        "speed_mean_mps": round(speed, 2), "loc_confidence_min": round(loc_conf, 2),
        "response_latency_s": "",
    }, cat, cause_stated, pattern


def fari_report(rng, ts):
    area = rng.choice(list(FARI_AREAS))
    cat = pick(rng, FARI_MIX)
    pattern = ""
    latency = rng.uniform(0.8, 2.0)
    if cat == "U2":                            # P4: response-delay complaints after update
        p_delay = 0.6 if ts >= FARI_UPDATE else 0.2
        if rng.random() < p_delay:
            template, pattern = rng.choice(FARI_T["U2_delay"]), "P4"
            latency = rng.uniform(4.0, 9.0)
        else:
            template = rng.choice(FARI_T["U2_other"])
    else:
        template = rng.choice(FARI_T[cat])
    cause_stated = template.endswith("| cause")
    text = fill(rng, template.replace(" | cause", ""))
    lat, lon = FARI_AREAS[area]                # coarse area only, never a home address
    return {
        "platform": "Fari", "site": area, "zone": "",
        "lat": lat, "lon": lon, "temperature_c": "",
        "author_role": pick(rng, FARI_AUTHORS), "text": text,
        "battery_pct": round(rng.uniform(20, 100), 1), "battery_drop_pct_1h": "",
        "motor_current_mean_a": "", "motor_current_trend_a_per_h": "",
        "speed_mean_mps": "", "loc_confidence_min": "",
        "response_latency_s": round(latency, 2),
    }, cat, cause_stated, pattern


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    reports, key = [], []
    span = int((END - START).total_seconds())
    for i in range(args.n):
        ts = START + timedelta(seconds=rng.randrange(span))
        is_fari = rng.random() < SHARE_FARI
        row, cat, cause, pattern = (fari_report if is_fari else rover_report)(rng, ts)

        secondary = ""
        if cat != "NO_INCIDENT" and rng.random() < 0.12:   # mixed issues in one note
            secondary = rng.choice([c for c in SECONDARY_T if c != cat])
            row["text"] = row["text"].rstrip(".") + ", " + SECONDARY_T[secondary]
        row["text"] = add_noise(rng, row["text"])

        rid = f"R{i + 1:05d}"
        reports.append({"report_id": rid, "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                        **row, "is_synthetic": True})
        sev = 1 + rng.choices(range(4), weights=SEVERITY[cat])[0]
        key.append({"report_id": rid, "true_category": cat,
                    "secondary_category": secondary, "severity": sev,
                    "root_cause_stated": cause, "planted_pattern": pattern})

    reports.sort(key=lambda r: r["timestamp"])
    DATA.mkdir(exist_ok=True)
    SEALED.mkdir(exist_ok=True)
    write_csv(DATA / "field_reports.csv", reports)
    write_csv(SEALED / "answer_key.csv", key)
    digest = hashlib.sha256((SEALED / "answer_key.csv").read_bytes()).hexdigest()
    print(f"wrote {len(reports)} reports; answer key sha256 = {digest}")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
