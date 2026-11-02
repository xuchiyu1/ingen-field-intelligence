"""Build W03_Findings_Report.docx from the Week 3 result files.

Reads results/w03/*.json|csv and the figures written by w03_trends.py,
w03_hotspots.py, w03_telemetry.py and w03_answer_key.py.

Usage: python src/make_findings_report.py
"""

import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
W03 = ROOT / "results/w03"


def load(name):
    return json.loads((W03 / name).read_text())


def table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for cell, h in zip(t.rows[0].cells, header):
        cell.text = h
    for row in rows:
        for cell, v in zip(t.add_row().cells, row):
            cell.text = str(v)


def finding(doc, n, title, evidence, confidence, caveat, action):
    doc.add_heading(f"F{n}. {title}", 2)
    doc.add_paragraph(evidence)
    for label, text in (("Confidence", confidence), ("Caveat", caveat), ("Recommended action", action)):
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(label + ": ").bold = True
        p.add_run(text)


def main():
    tr, hs, te, ak = (load(f) for f in ("trends_summary.json", "hotspots.json",
                                        "telemetry_summary.json", "answer_key_check.json"))
    cv = pd.read_csv(W03 / "telemetry_cv.csv").set_index("target")
    themes = pd.read_csv(W03 / "fari_u2_themes.csv", index_col=0)
    sev = pd.read_csv(W03 / "severity_by_category.csv")
    cold, fari, p1 = tr["cold_battery"], tr["fari"], ak["P1_navigation_hotspot"]
    kv = ak["classifier_vs_generator"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("W03 Findings Report: Field Incident Patterns", 0)
    doc.add_paragraph("inGen Dynamics · Applied AI Analyst Intern · Chiyu Xu")

    doc.add_heading("Summary", 1)
    for line in [
        f"Cold weather: below 0 °C the Rover battery-incident rate is {cold['h1_rate_ratio_cold_vs_warm']}× "
        f"the rate at warmer temperatures (95% CI {cold['ci'][0]}–{cold['ci'][1]}).",
        f"Fari: response-delay complaints rose {fari['delay_rate_ratio_after_vs_before']}× per active hour "
        f"after the 1 April update (95% CI {fari['ci'][0]}–{fari['ci'][1]}); mean latency "
        f"{fari['mean_latency_s_before']} s → {fari['mean_latency_s_after']} s.",
        "Telemetry: rising motor current in the hour before a sensor (H3) fault is a strong early signal "
        f"(cross-validated AUC {cv.loc['H3', 'auc_mean']:.2f}); battery, speed and localisation signals "
        "also separate their categories, but most software, access and human categories leave no trace.",
        f"Hotspot: Site_C North has the fleet's highest navigation-incident rate ({p1['found_with_predicted_labels']['rr']}× "
        "the fleet) but it does not survive multiple-testing correction. It is a lead, not a confirmed finding.",
        "Answer-key check: 3 of 4 planted patterns found, 1 partial. The partial miss is caused by sample "
        "size, not by the classifier.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_heading("Data and method", 1)
    doc.add_paragraph(
        "2,000 synthetic field reports (1,574 Aido Rover, 426 Fari, Jan–Jun 2026), classified by the frozen "
        f"Week 2 prompt (0 flagged). Rates use operating hours from data/exposure_hours.csv "
        f"({tr['rover_hours']:,} Rover hours); telemetry is compared with {te['normal_windows']:,} "
        "no-incident Rover windows from data/normal_telemetry.csv. Both supplementary files were generated "
        "after the corpus from stated assumptions (see data/README.md). Every comparison has a 95% interval "
        "or test; tests across many categories, sites or zones are corrected with Benjamini-Hochberg. "
        "The sealed answer key was opened only after all analyses were final.")

    doc.add_heading("Findings", 1)
    finding(doc, 1, "Cold weather doubles the battery-incident rate",
            f"{cold['h1_reports_cold']} of {cold['h1_reports_cold'] + cold['h1_reports_warm']} H1 battery "
            f"reports happened below 0 °C, during an estimated {cold['share_of_time_below_0c']:.0%} of operating "
            f"time. Rate ratio {cold['h1_rate_ratio_cold_vs_warm']} (95% CI {cold['ci'][0]}–{cold['ci'][1]}, "
            f"p = {cold['p']:.4f}). Battery incidents also trend down from January to June "
            "(not significant after correction), consistent with warming weather.",
            "High.", "Time below 0 °C is estimated from the normal-telemetry sample, not logged directly.",
            "Pre-warm or top up batteries before cold night patrols; add a cold-weather battery alert threshold.")
    finding(doc, 2, "Fari response delays rose sharply after the 1 April update",
            f"Delay-theme complaints: {fari['delay_per_100h_before']} → {fari['delay_per_100h_after']} per 100 "
            f"active hours (rate ratio {fari['delay_rate_ratio_after_vs_before']}, 95% CI "
            f"{fari['ci'][0]}–{fari['ci'][1]}). Hour-before latency for all U2 complaints averages "
            f"{te['fari_u2_latency_s']} s vs {te['fari_normal_latency_s']} s in normal hours. "
            f"Example: \"{fari['example_quotes']['response delay']}\"",
            "High.", "A before/after comparison cannot by itself prove the update caused it.",
            "Check the April release for latency regressions; add a latency alert (e.g. > 3 s for an hour).")
    doc.add_paragraph("Share of Fari U2 complaints by theme (keyword coding):")
    table(doc, ["Theme", "Before 1 Apr", "After 1 Apr"],
          [(t, f"{r.before_apr1:.0%}", f"{r.after_apr1:.0%}") for t, r in themes.iterrows() if t != "other"])
    doc.add_picture(str(ROOT / "figures/w03_weekly_rates.png"), width=Inches(6.3))

    finding(doc, 3, "Rising motor current is an early warning for sensor faults",
            f"In the hour before an H3 sensor report, motor current is "
            f"{next(e['diff'] for e in te['large_effects_q05_d08'] if e['category'] == 'H3' and e['feature'] == 'motor_current_mean_a'):.1f} A "
            "higher than normal and its trend is about +1.3 A/h vs 0 (Cohen's d 4.4). A 5-fold cross-validated "
            f"logistic regression separates these hours from normal ones with AUC {cv.loc['H3', 'auc_mean']:.2f}. "
            "This is the least obvious link in the data: the failure is a sensor, the signal is in the drive.",
            "Medium-high: very strong in this data, mechanism not explained.",
            "Synthetic telemetry; real signals will be noisier, so AUC here is an upper bound.",
            "Validate on real telemetry; if it holds, alert maintenance when motor current trends up > 0.8 A/h.")
    doc.add_picture(str(ROOT / "figures/w03_motor_current.png"), width=Inches(6.3))

    finding(doc, 4, "Telemetry predicts some incident types well and most not at all",
            f"Per-category AUC: H1 battery {cv.loc['H1', 'auc_mean']:.2f}, E2 terrain {cv.loc['E2', 'auc_mean']:.2f}, "
            f"S1 navigation {cv.loc['S1', 'auc_mean']:.2f}, E1 weather {cv.loc['E1', 'auc_mean']:.2f}; but "
            f"S2 obstacle, S3 connectivity, S4 app, E3 access, U1 interference ≈ 0.5 (chance). Any incident vs "
            f"normal: AUC {cv.loc['any incident', 'auc_mean']:.2f}.",
            "High for the split; the per-category numbers depend on the synthetic generator.",
            "High AUCs partly restate the label (low battery → battery incident); they show detection, not prediction.",
            "Use telemetry alerts for battery, terrain and localisation; rely on reports for the rest.")

    finding(doc, 5, "Navigation hotspot at Site_C North: a lead, not a finding",
            f"Site_C North has the highest S1 rate of 25 zones, rate ratio {p1['found_with_predicted_labels']['rr']} "
            f"(95% CI {p1['found_with_predicted_labels']['ci'][0]}–{p1['found_with_predicted_labels']['ci'][1]}, "
            f"unadjusted p = {p1['found_with_predicted_labels']['p']}). After correcting for 25 zones q = "
            f"{p1['found_with_predicted_labels']['q_bh_25_zones']}; across all categories {len(hs['unadjusted_p05'])} "
            "zone-category cells pass p < 0.05, about what chance alone would give (350 tests × 0.05 ≈ 17). "
            "Getis-Ord Gi* was run (500 m band) but with 1–4 neighbours per zone its permutation p-values "
            "are unstable, so it is reported only as context.",
            "Low.", "Only ~63 Rover reports per zone over six months.",
            "Treat Site_C North as a hypothesis: collect another quarter of data or run a targeted check "
            "(GPS logs, map quality) there, then test that one zone.")
    doc.add_picture(str(ROOT / "maps/w03_s1_hotspot.png"), width=Inches(6.3))

    top_sev = sev[(sev.platform == "Aido Rover") & (sev.reports >= 50)].head(4)
    finding(doc, 6, "Dock, interference and sensor incidents are the most serious",
            "Share of incidents rated severity 3–4 (Rover): " + "; ".join(
                f"{r.category} {r.share_sev_3_4:.0%}" for r in top_sev.itertuples()) + ".",
            "Low.", "Severity is predicted by the model; Week 2 showed weak agreement with hand labels, and "
            "the answer-key check (F8) shows severity is not recoverable from the text in this corpus.",
            "Do not prioritise from these severity numbers until severity is reported in a structured field.")

    finding(doc, 7, "The weather-pause rule is the classifier's main systematic error",
            f"Against the generator labels the classifier is {kv['category_accuracy']:.1%} accurate on all 2,000 "
            f"reports (Week 2 held-out: 96.0%). The largest confusion, E1 weather → NO_INCIDENT "
            f"({kv['top_confusions'].get('E1->NO_INCIDENT', 0)} reports), is the same taxonomy gap found in Week 2: "
            "a patrol paused by the weather rule can be read as either.",
            "High.", "Generator labels are themselves a design choice, not ground truth.",
            "Add one sentence to the Taxonomy Guide: a weather-rule pause is E1 (severity 2), not NO_INCIDENT.")

    doc.add_heading("Answer-key check (sealed key opened after the analysis)", 1)
    table(doc, ["Planted pattern", "Result", "Evidence"], [
        ("P1 Site_C North navigation", "Partial (missed after correction)",
         f"rank 1 of 25, RR {p1['found_with_predicted_labels']['rr']}, q {p1['found_with_predicted_labels']['q_bh_25_zones']}; "
         f"true labels give RR {p1['with_true_labels']['rr']}, q {p1['with_true_labels']['q_bh_25_zones']}"),
        ("P2 Cold-weather battery", "Found", f"RR {cold['h1_rate_ratio_cold_vs_warm']}, CI {cold['ci']}"),
        ("P3 Motor current before sensor faults", "Found",
         f"trend +{ak['P3_motor_current_before_sensor_faults']['found_trend_diff_a_per_h']} A/h, d "
         f"{ak['P3_motor_current_before_sensor_faults']['cohens_d']}"),
        ("P4 Fari delay after update", "Found", f"RR {fari['delay_rate_ratio_after_vs_before']}, CI {fari['ci']}"),
    ])
    finding(doc, 8, "The one miss is a sample-size problem, not a classifier problem",
            f"With the generator's true labels P1 is still not significant (q {p1['with_true_labels']['q_bh_25_zones']}), "
            "so a better classifier would not have found it. Separately, predicted severity matches the "
            f"generator only {kv['severity_exact']:.0%} exactly ({kv['severity_within_1']:.0%} within one level): "
            "the generator drew severity at random per category, independent of the text, so no text-based "
            "model could recover it. This partly explains the weak severity agreement in Week 2.",
            "High.", "Specific to how this synthetic corpus was generated.",
            "For zone-level questions, plan sample size up front; fix the generator so severity follows the text.")

    doc.add_heading("Limitations", 1)
    for line in [
        "All data is synthetic, including exposure hours and normal telemetry; findings show what the method "
        "can detect, not real fleet behaviour.",
        "Public review snippets were not collected, so external feedback themes are not covered.",
        "Fari locations are coarse areas only (privacy rule), so no Fari hotspot analysis was attempted.",
        "Keyword theme coding for Fari complaints was checked by reading examples, not against hand labels.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    out = ROOT / "W03_Findings_Report.docx"
    doc.save(out)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
