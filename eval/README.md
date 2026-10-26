# Gold evaluation set

`gold_set.csv`: 250 reports (200 Aido Rover, 50 Fari) drawn by `src/sample_gold_set.py` (seed 7).

- **Labelling rule:** fill `label_*` columns using only `W01_Taxonomy_Guide.docx`, never `data/sealed/answer_key.csv`.
- **Splits:** `tuning` (150) for prompt iteration in Week 2; `heldout` (100) used once for the final accuracy number.
- **Agreement:** the 50 rows with `double_label = yes` are labelled again a few days later in `round2_*`; Cohen's kappa is reported per category. Low agreement means the rule needs fixing, not just the label.
- `borderline` / `notes`: record reports that do not fit cleanly; they feed back into the Taxonomy Guide.

## How to label
1. `python src/build_label_tool.py`, then open `eval/label_tool.html` in a browser (offline; labels autosave in the browser).
2. Round 1: label all 250, then **Export CSV** and run `python src/import_labels.py ~/Downloads/gold_labels_round1.csv`.
3. A few days later, switch to Round 2 (50 reports, round-1 answers hidden), export, and import `gold_labels_round2.csv`.
4. `python src/evaluate.py --agreement` for Cohen's kappa.
