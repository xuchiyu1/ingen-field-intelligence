# inGen Field Intelligence

LLM-assisted classification of unstructured robot field reports into a governed incident taxonomy.
Applied AI Analyst Internship, inGen Dynamics (Futurenauts Internship Program). Author: Chiyu Xu.

**Primary platform:** Aido Rover (outdoor patrol). **Secondary:** Fari (indoor eldercare companion).

**Version 1.0.** Every figure and report rebuilds from one command. All data is synthetic.

## Quickstart
```bash
pip install -r requirements.txt
python run_all.py            # data -> evaluation -> analysis -> reports, about 30 seconds
python run_all.py --live     # also re-run LLM classification with `claude -p` (hours)
```
Without `--live`, LLM predictions are read from `results/` and `data/classified_corpus.csv`, because an LLM run is slow, costs money and is not bit-for-bit repeatable. The hand-labelled gold set is never regenerated. The run ends by checking the sealed answer key's sha256.

## Results at a glance
| System (100 held-out gold reports, run once) | Category accuracy |
|---|---|
| **LLM classifier** (`prompts/classify_v1.md`, claude-opus-4-7) | **96.0%** |
| Keyword rules | 94.0% |
| TF-IDF + logistic regression | 78.0% |

| Week 3 finding | Evidence |
|---|---|
| Cold weather raises battery incidents | 1.8× the rate below 0 °C (95% CI 1.32–2.45) |
| Fari response-delay complaints after the 1 April update | 5.0× per active hour (95% CI 2.8–9.1); latency 1.75 s → 3.04 s |
| Motor current rises before sensor faults | cross-validated AUC 0.996 |
| Site_C North navigation hotspot | highest rate (2.1×) but not significant after correction (q = 0.33) |
| Sealed answer key | 3 of 4 planted patterns found, 1 partial (limited by sample size) |

## Known limitations
- All reports, exposure hours and telemetry are synthetic; results show what the method can detect, not real fleet behaviour.
- Gold labels come from one labeller; kappa 1.0 was a same-day re-label and overstates reliability.
- Predicted severity is weak (47% exact vs hand labels); the generator drew severity independently of the text.
- About 63 Rover reports per patrol zone is too few to confirm zone-level hotspots.
- Public review snippets were not collected.

## Configuration
| Setting | Where | Default |
|---|---|---|
| Corpus size, seed | `src/generate_corpus.py --n --seed` | 2000, 42 |
| Exposure / normal telemetry seed | `src/generate_exposure.py --seed` | 2026 |
| Gold-set sample seed | `src/sample_gold_set.py --seed` (do not rerun: overwrites hand labels) | 7 |
| Prompt version | `prompts/<name>.md`, `--prompt` | `classify_v1` |
| LLM backend, model | `src/classify_llm.py --backend api\|claude-cli --model` | `api` (all reported runs used `claude-cli`), Opus |
| API key | `ANTHROPIC_API_KEY` environment variable, `--backend api` only; never committed | — |
| Hotspot neighbour distance | `BAND_M` in `src/w03_hotspots.py` | 500 m |
| Human-review accuracy floor | `src/make_eval_report.py --review-floor` | 0.8 |

## Week 1: Data Landscape, Incident Taxonomy, Corpus & Gold Set

| Deliverable | Status |
|---|---|
| [`W01_Data_Landscape.docx`](W01_Data_Landscape.docx): text sources per platform, who writes them, decisions supported, privacy constraints, scope | Done (v1) |
| [`W01_Taxonomy_Guide.docx`](W01_Taxonomy_Guide.docx): 14 incident categories in 4 groups + NO_INCIDENT, decision rules, examples, borderline rulings, severity scale (1–4), root-cause flag, benchmark notes | Done (v1) |
| [`weekly/Wk-01-Log.md`](weekly/Wk-01-Log.md): the hardest category boundary (AI Detection Error vs Sensors) | Done |
| [`data/`](data/): 2,000 synthetic Aido Rover and Fari reports with telemetry and four planted patterns; sealed answer key ([generator](src/generate_corpus.py)) | Done (public review sample to add) |
| [`eval/gold_set.csv`](eval/gold_set.csv): 250 reports (150 tuning / 100 held-out, 50 double-labelled), sampled by [`src/sample_gold_set.py`](src/sample_gold_set.py) | Done: 250/250 hand-labelled, 50 double-labelled |

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

## Week 3: Trends, Geospatial Hotspots, Telemetry & Answer-Key Check

| Deliverable | Status |
|---|---|
| [`src/generate_exposure.py`](src/generate_exposure.py): operating hours and no-incident telemetry, generated after the corpus (see [`data/README.md`](data/README.md)) | Done |
| [`src/w03_trends.py`](src/w03_trends.py): incident rates per 100 operating hours, quasi-Poisson weekly trends, site comparison, cold-weather battery, severity, Fari complaint themes | Done |
| [`src/w03_hotspots.py`](src/w03_hotspots.py): zone rates vs fleet (exact test, BH) and Getis-Ord Gi*; [`maps/w03_s1_hotspot.png`](maps/w03_s1_hotspot.png) | Done |
| [`src/w03_telemetry.py`](src/w03_telemetry.py): pre-incident vs normal telemetry (Welch CI, Cohen's d, BH) and 5-fold cross-validated classifier | Done |
| [`src/w03_answer_key.py`](src/w03_answer_key.py): opens the sealed key (sha256 checked) after the analysis; 3 of 4 planted patterns found, 1 partial | Done |
| [`W03_Findings_Report.docx`](W03_Findings_Report.docx): 8 findings with evidence, confidence, caveats and actions | Done |
| [`weekly/Wk-03-Log.md`](weekly/Wk-03-Log.md) | Done |

## Week 4: Governance, Packaging & Delivery

| Deliverable | Status |
|---|---|
| `run_all.py` + `requirements.txt`: one-command rebuild (tag `v1.0`) | Done |
| [`W04_Governance_Pack.docx`](W04_Governance_Pack.docx): data dictionary (checked against the files), processing rules, taxonomy change process, monthly re-evaluation, maintenance guide ([builder](src/make_governance_pack.py)) | Done |
| [`W04_Findings_Deck.pptx`](W04_Findings_Deck.pptx) + PDF: 8 slides, every title a finding, numbers read from the results ([builder](src/make_deck.js)) | Draft |
| `W04_Retrospective.docx`: 1 page | To do |

**Week 3 run order:**
```bash
pip install geopandas esda libpysal statsmodels
python src/generate_exposure.py --seed 2026
python src/w03_trends.py && python src/w03_hotspots.py && python src/w03_telemetry.py
python src/w03_answer_key.py          # only after the analyses are final
python src/make_findings_report.py
```

## Repository structure
```
├── run_all.py              # one command: rebuild data, evaluation, analysis, reports
├── requirements.txt
├── W01_*.docx, W02_*.docx, W03_*.docx, W04_*   # weekly deliverables
├── src/       # generators, classifier, baselines, evaluation, Week 3 analysis, report builders
├── prompts/   # versioned classification prompts + CHANGELOG
├── data/      # synthetic corpus, exposure, normal telemetry; sealed/ holds the answer key
├── eval/      # hand-labelled gold set and the offline labelling tool
├── results/   # predictions, run logs, error files; w03/ holds analysis outputs
├── figures/, maps/          # charts and the hotspot map
└── weekly/    # weekly logs
```

All data in this repository is synthetic. No personal data is included.
