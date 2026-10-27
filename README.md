# inGen Field Intelligence

LLM-assisted classification of unstructured robot field reports into a governed incident taxonomy.
Applied AI Analyst Internship, inGen Dynamics (Futurenauts Internship Program). Author: Chiyu Xu.

**Primary platform:** Aido Rover (outdoor patrol). **Secondary:** Fari (indoor eldercare companion).

## Week 1: Data Landscape, Incident Taxonomy, Corpus & Gold Set

| Deliverable | Status |
|---|---|
| [`W01_Data_Landscape.docx`](W01_Data_Landscape.docx): text sources per platform, who writes them, decisions supported, privacy constraints, scope | Done (v1) |
| [`W01_Taxonomy_Guide.docx`](W01_Taxonomy_Guide.docx): 14 incident categories in 4 groups + NO_INCIDENT, decision rules, examples, borderline rulings, severity scale (1–4), root-cause flag, benchmark notes | Done (v1) |
| [`weekly/Wk-01-Log.md`](weekly/Wk-01-Log.md): the hardest category boundary (AI Detection Error vs Sensors) | Done |
| [`data/`](data/): 2,000 synthetic Aido Rover and Fari reports with telemetry and four planted patterns; sealed answer key ([generator](src/generate_corpus.py)) | Done (public review sample to add) |
| [`eval/gold_set.csv`](eval/gold_set.csv): 250 reports (150 tuning / 100 held-out, 50 double-labelled), sampled by [`src/sample_gold_set.py`](src/sample_gold_set.py) | Sampled, hand-labelling in progress |

### Key taxonomy decisions
1. Classify by **where the robot failed**, not by the trigger; the trigger is recorded in the root-cause flag.
2. Added **S5 AI Detection Error**: sensors and software work, but the AI's judgement is wrong (e.g., Fari false fall alerts).
3. **NO_INCIDENT** covers designed behaviour and safety rules working as intended.
4. Privacy and consent issues are handled as data governance (Data Landscape), not as robot incidents.

## Week 2: LLM Classification Pipeline, Evaluation & Error Analysis

| Deliverable | Status |
|---|---|
| [`src/classify_llm.py`](src/classify_llm.py) + [`prompts/classify_v1.md`](prompts/classify_v1.md): LLM classifier with schema-validated JSON output, retry/flagging, versioned prompt, token and cost logging | Built |
| [`src/baseline.py`](src/baseline.py): keyword-rule baseline and TF-IDF + logistic regression baseline | Built; keyword baseline run on held-out split |
| [`src/evaluate.py`](src/evaluate.py): accuracy, per-category precision/recall, confusion matrix, severity agreement, Cohen's kappa, error file | Done: kappa 1.0 (same-day re-label, see report) |
| [`src/make_eval_report.py`](src/make_eval_report.py): builds `W02_Evaluation_Report.docx` (held-out accuracy vs baselines, per-category results, kappa, human-review threshold, error causes, cost) | Done: `W02_Evaluation_Report.docx` |
| [`prompts/CHANGELOG.md`](prompts/CHANGELOG.md): prompt versions and their tuning-split effect | Started |
| [`weekly/Wk-02-Log.md`](weekly/Wk-02-Log.md) | Done |
| [`W02_Evaluation_Report.docx`](W02_Evaluation_Report.docx): held-out accuracy **LLM 96.0%** vs keyword 94.0% vs TF-IDF 78.0%, per-category results, human-review threshold, error causes | Done |
| `data/classified_corpus.csv`: full corpus classified with the final prompt | Done (2,000 reports, 0 flagged) |

**Week 2 run order** (once the gold set is labelled):
1. `python src/evaluate.py --agreement`: Cohen's kappa; fix any rule with kappa below 0.6
2. `python src/baseline.py --method keyword --split heldout` and `python src/baseline.py --method tfidf`
3. `python src/classify_llm.py --input eval/gold_set.csv --split tuning`, then iterate prompts on tuning only (log in `prompts/CHANGELOG.md`)
4. `python src/classify_llm.py --input eval/gold_set.csv --split heldout --prompt <final>`, run **once**
5. `python src/evaluate.py results/llm_<final>_gold_set_heldout.csv --split heldout`, then fill `error_cause` in the errors file
6. `python src/make_eval_report.py --prompt <final>`
7. `python src/classify_llm.py --input data/field_reports.csv --save-corpus --prompt <final>`

```bash
pip install anthropic scikit-learn python-docx
export ANTHROPIC_API_KEY=...   # never committed
python src/baseline.py --method keyword --split heldout
python src/classify_llm.py --input eval/gold_set.csv --split tuning
python src/evaluate.py results/llm_classify_v1_gold_set_tuning.csv --split tuning
```

## Repository structure
```
├── W01_Data_Landscape.docx
├── W01_Taxonomy_Guide.docx
├── src/         # corpus generator, gold-set sampler, classifier, baselines, evaluation
├── prompts/     # versioned classification prompts
├── results/     # predictions, run logs, error files
├── data/        # synthetic corpus; sealed/ holds the answer key (Week 3)
├── eval/        # gold evaluation set
└── weekly/      # weekly logs
```

All data in this repository is synthetic. No personal data is included.
