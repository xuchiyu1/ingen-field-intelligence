"""Build W04_Governance_Pack.docx: how to run and maintain this pipeline on real reports.

The data dictionary is checked against the real files: the script stops if any
column in a data or results file is missing from FIELDS, so the dictionary
cannot silently fall out of date.

Usage: python src/make_governance_pack.py
"""

import csv
import json
from pathlib import Path

from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent.parent

FILES = {  # file: (what it is, who writes it)
    "data/field_reports.csv": ("One row per field report: metadata, free text, hour-before telemetry",
                               "src/generate_corpus.py (real data: ingestion job)"),
    "data/classified_corpus.csv": ("field_reports.csv plus the LLM prediction and its provenance",
                                   "src/classify_llm.py --save-corpus"),
    "data/exposure_hours.csv": ("Operating hours per week and site-zone (Rover) or area (Fari)",
                                "src/generate_exposure.py (real data: fleet operations log)"),
    "data/normal_telemetry.csv": ("One-hour telemetry windows with no incident report",
                                  "src/generate_exposure.py (real data: telemetry store)"),
    "eval/gold_set.csv": ("Hand-labelled evaluation reports with split and second-round labels",
                          "src/sample_gold_set.py, then hand labelling"),
    "data/sealed/answer_key.csv": ("Generator labels and planted patterns (synthetic data only)",
                                   "src/generate_corpus.py"),
    "results/llm_classify_v1_gold_set_heldout.csv": ("Predictions for one run (same format for every run "
                                                     "and baseline)", "src/classify_llm.py, src/baseline.py"),
    "results/llm_classify_v1_gold_set_heldout_errors.csv": ("Misclassified gold reports with the reviewed "
                                                            "cause", "src/evaluate.py, then hand review"),
}

FIELDS = {
    "report_id": "Unique report ID (R00001…)",
    "window_id": "Unique normal-telemetry window ID (N00001…)",
    "timestamp": "Local time of the report or window start (YYYY-MM-DD HH:MM)",
    "platform": "Aido Rover or Fari",
    "site": "Rover patrol site (Site_A–E) or Fari coarse area (Area_1–3); never a home address",
    "zone": "Rover patrol zone (North/South/East/West/Dock); empty for Fari",
    "lat": "Latitude: Rover position in zone; Fari area centroid only",
    "lon": "Longitude, as lat",
    "temperature_c": "Ambient temperature in °C (Rover)",
    "author_role": "Who wrote the report: operator, technician, guard; care_staff, family, resident_via_staff",
    "text": "Free-text report as written; personal names must be removed before storage",
    "battery_pct": "Battery charge %, hour before the report",
    "battery_drop_pct_1h": "Battery drop in percentage points over that hour (Rover)",
    "motor_current_mean_a": "Mean drive-motor current in amps (Rover)",
    "motor_current_trend_a_per_h": "Change in motor current, amps per hour (Rover)",
    "speed_mean_mps": "Mean speed, metres per second (Rover)",
    "loc_confidence_min": "Lowest localisation confidence 0–1 in the hour (Rover)",
    "response_latency_s": "Mean response latency in seconds (Fari)",
    "is_synthetic": "True for every row in this repository",
    "pred_category": "Predicted taxonomy code (H1–H4, S1–S5, E1–E3, U1–U2, NO_INCIDENT); empty if flagged",
    "pred_severity": "Predicted severity 1–4 (Taxonomy Guide scale)",
    "pred_root_cause_stated": "True if the report itself states why it happened",
    "confidence": "Model self-rated confidence: high / medium / low; low and medium go to human review "
                  "when below the accuracy floor",
    "reason": "One-sentence model justification",
    "flag": "Empty if valid; otherwise why the output was rejected (invalid JSON, usage limit, …)",
    "prompt_version": "Prompt file used (prompts/<version>.md)",
    "model": "Model ID actually used, from the run log",
    "week_start": "Monday of the week (exposure)",
    "operating_hours": "Hours in operation that week for the site-zone or area",
    "split": "tuning (prompt development) or heldout (final score, run once)",
    "double_label": "yes if the report is labelled twice for Cohen's kappa",
    "label_category": "Hand label, round 1",
    "label_severity": "Hand severity, round 1",
    "label_root_cause_stated": "Hand root-cause flag (yes/no)",
    "borderline": "yes if the labeller found the rule unclear",
    "notes": "Labeller notes on borderline cases",
    "round2_category": "Hand label, round 2 (double-label rows only)",
    "round2_severity": "Hand severity, round 2",
    "true_category": "Generator category (synthetic only)",
    "secondary_category": "Second issue mixed into the text, if any",
    "severity": "Generator severity (drawn independently of the text)",
    "root_cause_stated": "Generator root-cause flag",
    "planted_pattern": "P1–P4 if the row carries a planted pattern",
    "gold": "Gold label of a misclassified report",
    "pred": "Predicted label of a misclassified report",
    "error_cause": "Reviewed cause: rule unclear / genuinely ambiguous / multiple issues / model misreading / "
                   "gold label wrong",
}


def table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for cell, h in zip(t.rows[0].cells, header):
        cell.text = h
    for row in rows:
        for cell, v in zip(t.add_row().cells, row):
            cell.text = str(v)


def bullets(doc, lines, style="List Bullet"):
    for line in lines:
        doc.add_paragraph(line, style=style)


def main():
    columns = {f: next(csv.reader(open(ROOT / f, encoding="utf-8"))) for f in FILES}
    missing = sorted({c for cols in columns.values() for c in cols} - set(FIELDS))
    if missing:
        raise SystemExit(f"undocumented columns: {missing}")
    run_log = json.loads((ROOT / "results/llm_classify_v1_gold_set_heldout.json").read_text())
    corpus_log = json.loads((ROOT / "results/llm_classify_v1_field_reports_batch25.json").read_text())
    ratio = ((run_log["estimated_cost_usd"] / run_log["n_reports"])
             / (corpus_log["estimated_cost_usd"] / corpus_log["n_reports"]))

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("W04 Governance Pack: Field-Report Classification Pipeline", 0)
    doc.add_paragraph("inGen Dynamics · Applied AI Analyst Intern · Chiyu Xu · applies to repository v1.0")
    doc.add_paragraph(
        "What InGen needs to run this pipeline on real field reports after the internship: what every "
        "field means, how raw text becomes a classified record, how the taxonomy may change, how accuracy "
        "is re-checked each month, and how the model, prompts and costs are maintained.")

    doc.add_heading("1. Data dictionary", 1)
    table(doc, ["File", "Contents", "Written by"], [(f, *v) for f, v in FILES.items()])
    doc.add_paragraph()
    seen = []
    for cols in columns.values():
        seen += [c for c in cols if c not in seen]
    table(doc, ["Field", "Meaning", "Appears in"],
          [(c, FIELDS[c], ", ".join(Path(f).name for f, cols in columns.items() if c in cols))
           for c in seen])

    doc.add_heading("2. Processing rules: raw text to classified record", 1)
    bullets(doc, [
        "Ingest: one row per report with report_id, timestamp, platform, site/zone and text. Attach the "
        "hour-before telemetry by unit and timestamp.",
        "Privacy, before anything is stored or sent to a model: remove personal names, phone numbers and "
        "addresses from text; store Fari locations as coarse areas only; never store resident identities.",
        "Classify with the current frozen prompt (prompts/<version>.md). Output must match the JSON schema "
        "(category, severity, root_cause_stated, reason, confidence) and is validated again on arrival.",
        "Invalid output is retried once, then flagged with the reason. A flagged report is never guessed. "
        "Rerun flagged reports with --retry-flagged.",
        "Store the prediction with prompt_version and model, so every record can be traced to the rules "
        "that produced it.",
        "Route to human review any confidence band whose measured accuracy is below the floor (default 80%). "
        "On the held-out set every band met the floor; low-confidence outputs were 1.6% of the full corpus.",
        "Analysis uses rates per operating hour, never raw counts, and corrects for multiple testing when "
        "comparing many sites, zones or categories.",
    ], "List Number")

    doc.add_heading("3. Taxonomy change process", 1)
    doc.add_paragraph("Roles: anyone (field staff, analysts, engineering) may propose a change. The taxonomy "
                      "owner (analytics lead) decides, with the engineering lead for hardware and software "
                      "categories.")
    bullets(doc, [
        "Proposal: the problem with the current rules, 5 or more real example reports, and the proposed "
        "rule wording (new category, split, merge or clarified boundary).",
        "Decision within two weeks. Add a category only if it would hold at least ~2% of reports or "
        "drives a distinct action; otherwise clarify an existing rule.",
        "Update the Taxonomy Guide (new version number), and write a mapping from old to new codes so "
        "historical data stays comparable.",
        "Gold set: relabel every affected gold report and add at least 10 new examples of the changed "
        "category. Re-check agreement on them with a second labeller.",
        "Prompt: copy to a new version file (never edit a frozen prompt), tune on the tuning split only, "
        "record the change in prompts/CHANGELOG.md.",
        "Score the new prompt once on the held-out split. Ship only if overall accuracy does not fall and "
        "the changed categories meet the recall floor (0.8).",
        "Reclassify the corpus, rerun the analysis, and announce the change with its effective date.",
    ], "List Number")
    doc.add_paragraph("Open example: the weather-rule pause (E1 vs NO_INCIDENT) is the largest systematic "
                      "error (27 of 2,000 reports against the generator labels). It should go through this "
                      "process as the first clarified rule.")

    doc.add_heading("4. Monthly re-evaluation routine", 1)
    bullets(doc, [
        "Sample 50 reports from the month, stratified by platform, and hand-label them blind to the "
        "model output. Add them to a dated monitoring set (separate from the frozen held-out set).",
        "Compare model labels with the hand labels; also track the flag rate, the low-confidence share "
        "and the category mix against the previous three months.",
    ])
    table(doc, ["Signal", "Baseline (v1.0)", "Investigate when"], [
        ("Category accuracy on the monthly sample", "96.0% held-out", "below 90%, or 2 months below 93%"),
        ("Recall of any category with ≥ 5 monthly examples", "—", "below 0.8"),
        ("Flag rate after one retry", "0%", "above 1%"),
        ("Low-confidence share", "1.6%", "above 5%"),
        ("Category mix", "previous 3 months", "any category share doubles or halves"),
    ])
    doc.add_paragraph("When a signal fires: read the errors and assign causes (rule unclear, ambiguous, "
                      "multiple issues, model misreading, gold wrong). Rule problems go to the taxonomy "
                      "change process; model misreading goes to a new prompt version; a model update by the "
                      "provider is checked by rerunning the held-out split before switching.")

    doc.add_heading("5. Maintenance guide", 1)
    doc.add_heading("Model", 2)
    bullets(doc, [
        f"Reported runs used {run_log['model']} through Claude Code print mode (claude -p) on a Claude "
        "subscription. Production should use the Anthropic API (--backend api) with the API key in the "
        "ANTHROPIC_API_KEY environment variable, never in code or the repository.",
        "Pin the model ID. Before changing models, score the new one on the held-out split and compare "
        "accuracy, per-category recall and cost; record the decision in prompts/CHANGELOG.md.",
    ])
    doc.add_heading("Prompts", 2)
    bullets(doc, [
        "Prompts are versioned files; a frozen version is never edited. Every stored prediction names its "
        "prompt_version.",
        "The held-out split is used once per candidate prompt; repeated use turns it into a tuning set.",
    ])
    doc.add_heading("Costs", 2)
    table(doc, ["Run", "Reports", "Estimated cost (USD)", "Time"], [
        ("Held-out gold set, one report per call", run_log["n_reports"],
         f"{run_log['estimated_cost_usd']:.2f}", f"{run_log['seconds'] / 60:.0f} min"),
        ("Full corpus, 25 reports per call", corpus_log["n_reports"],
         f"{corpus_log['estimated_cost_usd']:.2f}", f"{corpus_log['seconds'] / 3600:.1f} h"),
    ])
    doc.add_paragraph("Costs are the claude -p equivalent list price; on a subscription they count against "
                      "usage limits instead of being charged. Batching 25 reports per call cut cost per "
                      f"report by about {ratio:.0f}×, because each call carries a fixed prompt overhead. "
                      "Every run writes a JSON log with tokens and cost next to its predictions.")
    doc.add_heading("Runbook", 2)
    table(doc, ["Problem", "What to do"], [
        ("Usage limit reached mid-run", "The run stops and flags the rest; after the reset, rerun the same "
                                        "command with --retry-flagged."),
        ("Not logged in / 401", "Log in to Claude Code (claude, then /login) or set a valid API key."),
        ("Rebuild everything", "python run_all.py (add --live to re-run the LLM)."),
        ("Answer-key hash changed", "The generator changed; regenerate deliberately and publish the new hash."),
    ])
    doc.add_heading("Ownership", 2)
    bullets(doc, ["Pipeline and prompts: analytics lead. Taxonomy decisions: analytics lead with the "
                  "engineering lead. Monthly labelling: one analyst, with a second labeller each quarter "
                  "for agreement. Costs and API keys: engineering."])

    out = ROOT / "W04_Governance_Pack.docx"
    doc.save(out)
    print(f"wrote {out.relative_to(ROOT)} ({len(seen)} fields documented)")


if __name__ == "__main__":
    main()
