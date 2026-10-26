# Prompt changelog

Every prompt version is a separate file. Each change is measured on the **tuning** split only and recorded here, including changes that did not help. The held-out split is run once, with the final version.

| Version | Change | Tuning accuracy | Notes |
|---|---|---|---|
| `classify_v1` | Initial prompt: taxonomy rules from W01_Taxonomy_Guide, labelling rules (where the robot failed; one primary category; NO_INCIDENT for designed behaviour), severity 1–4 aligned with the Concepts Primer definitions, root-cause rule | not yet run | Baseline version |
