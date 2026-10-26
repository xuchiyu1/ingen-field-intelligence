# Gold evaluation set

`gold_set.csv`: 250 reports (200 Aido Rover, 50 Fari) drawn by `src/sample_gold_set.py` (seed 7).

- **Labelling rule:** fill `label_*` columns using only `W01_Taxonomy_Guide.docx`, never `data/sealed/answer_key.csv`.
- **Splits:** `tuning` (150) for prompt iteration in Week 2; `heldout` (100) used once for the final accuracy number.
- **Agreement:** the 50 rows with `double_label = yes` are labelled again a few days later in `round2_*`; Cohen's kappa is reported per category. Low agreement means the rule needs fixing, not just the label.
- `borderline` / `notes`: record reports that do not fit cleanly; they feed back into the Taxonomy Guide.
