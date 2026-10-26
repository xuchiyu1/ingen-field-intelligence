# Prompt changelog

Every prompt version is a separate file. Each change is measured on the **tuning** split only and recorded here, including changes that did not help. The held-out split is run once, with the final version.

| Version | Change | Tuning accuracy | Notes |
|---|---|---|---|
| `classify_v1` | Initial prompt: taxonomy rules from W01_Taxonomy_Guide, labelling rules (where the robot failed; one primary category; NO_INCIDENT for designed behaviour), severity 1–4 aligned with the Concepts Primer definitions, root-cause rule | **99.3%** category (149/150); severity exact 50.7%, within one level 84.7% | Run 2026-10-26 via `claude -p` (claude-opus-4-7). Only category error: R01477 "heart-rate reading 49 BPM, resident was fine", gold NO_INCIDENT vs predicted S5; likely a gold-label error under the S5 rule. Severity disagreement is systematic (collisions labelled 4 by the labeller vs 1–2 by the model; "would not proceed" 2 vs 3), pointing to an unclear severity rule rather than a prompt fault. **Decision: freeze v1 as final.** Category accuracy is near ceiling, so further tuning would risk overfitting the tuning split; the severity rule issue is reported as a finding instead. |
