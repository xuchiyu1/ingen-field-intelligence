# Week 2 Log: Building the Classification Pipeline

**Chiyu Xu · Applied AI Analyst Intern · Week 2 (progress log)**

## What was built
- **LLM classifier** (`src/classify_llm.py`). Each report is sent to Claude with the taxonomy rules in a version-controlled prompt file (`prompts/classify_v1.md`). The response is constrained to a JSON schema (category, severity, root-cause flag, one-sentence reason, confidence) and validated again on arrival; invalid output is retried once and then flagged rather than guessed. Every run logs the model, prompt version, token counts and estimated cost, and the stable taxonomy prompt is cached to cut cost.
- **Non-LLM baselines** (`src/baseline.py`). A keyword rule set that needs no training data, and a TF-IDF + logistic regression model trained on the tuning split. The LLM has to beat these to justify its cost.
- **Evaluation harness** (`src/evaluate.py`). Overall accuracy, per-category precision, recall and F1, a confusion matrix, severity agreement, Cohen's kappa between my two labelling rounds, and an error file for grouping each error by cause.

## Results
On the 100 held-out gold reports, run once with the frozen prompt (classify_v1, claude-opus-4-7 via `claude -p`), the LLM classifier reached **96.0%** category accuracy. The keyword baseline reached 94.0% and the TF-IDF baseline 78.0%. On the tuning split the LLM scored 99.3%, which is why I froze v1 rather than tuning further.

Read honestly, the LLM's lead over the keyword baseline is two reports out of 100, which is not distinguishable from noise. The keyword rules were also written by the same person who wrote the generator templates, so that baseline is optimistically biased. Three of the four LLM errors trace back to overlapping taxonomy rules (weather-rule pauses fit both E1 and NO_INCIDENT; a speech-understanding complaint fits both U2 and S5), and the fourth is a report with two issues. The next fix belongs in the Taxonomy Guide, not the prompt. Severity is the weak dimension: 47% exact agreement and 83% within one level.

## The hardest design decision
Writing the keyword baseline forced the taxonomy's boundary rules into a fixed order: designed behaviour (NO_INCIDENT) and AI misjudgements (S5) have to be checked before hardware, and hardware faults before their environmental triggers. Otherwise "camera fogged in the rain" would always be classed as Weather. This is the same "classify by where the robot failed" rule from Week 1, now written as code. It also shows the limit of keywords: a report like "heart-rate reading 40 BPM, resident was fine" matches nothing that separates S5 from H3. That gap is exactly where an LLM should beat the baseline, and the S5/H3 rows are the first place I will look in the error analysis.

## Next
1. ~~Second labelling round and Cohen's kappa~~ Done: kappa 1.0 on 50 reports, but same-day re-labelling inflates this; a second labeller is the real test.
2. Clarify the E1/NO_INCIDENT and U2/S5 boundaries and the Level-4 severity rule in the Taxonomy Guide.
3. Week 3: trends, geospatial hotspots and telemetry on the fully classified corpus.
