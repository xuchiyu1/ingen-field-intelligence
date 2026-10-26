# Week 2 Log: Building the Classification Pipeline

**Chiyu Xu · Applied AI Analyst Intern · Week 2 (progress log)**

## What was built
- **LLM classifier** (`src/classify_llm.py`). Each report is sent to Claude with the taxonomy rules in a version-controlled prompt file (`prompts/classify_v1.md`). The response is constrained to a JSON schema (category, severity, root-cause flag, one-sentence reason, confidence) and validated again on arrival; invalid output is retried once and then flagged rather than guessed. Every run logs the model, prompt version, token counts and estimated cost, and the stable taxonomy prompt is cached to cut cost.
- **Non-LLM baselines** (`src/baseline.py`). A keyword rule set that needs no training data, and a TF-IDF + logistic regression model trained on the tuning split. The LLM has to beat these to justify its cost.
- **Evaluation harness** (`src/evaluate.py`). Overall accuracy, per-category precision, recall and F1, a confusion matrix, severity agreement, Cohen's kappa between my two labelling rounds, and an error file for grouping each error by cause.

## Status, stated plainly
No accuracy number is reported yet. The final number has to come from the 100 held-out gold reports, labelled by hand from the Taxonomy Guide, and that labelling is still in progress. The code has been tested end to end on placeholder labels only, so the pipeline is ready to score as soon as the gold set is complete. The LLM classifier still needs a valid API key before its first real run.

## The hardest design decision
Writing the keyword baseline forced the taxonomy's boundary rules into a fixed order: designed behaviour (NO_INCIDENT) and AI misjudgements (S5) have to be checked before hardware, and hardware faults before their environmental triggers. Otherwise "camera fogged in the rain" would always be classed as Weather. This is the same "classify by where the robot failed" rule from Week 1, now written as code. It also shows the limit of keywords: a report like "heart-rate reading 40 BPM, resident was fine" matches nothing that separates S5 from H3. That gap is exactly where an LLM should beat the baseline, and the S5/H3 rows are the first place I will look in the error analysis.

## Next
1. Finish hand-labelling the 250 gold reports, then the 50-report second round and kappa.
2. Run the TF-IDF baseline and the LLM classifier on the tuning split; iterate the prompt on tuning only, recording each change.
3. Run the final prompt once on the held-out split and report that number, with per-category results and an error analysis by cause.
