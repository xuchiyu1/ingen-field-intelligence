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

## Repository structure
```
├── W01_Data_Landscape.docx
├── W01_Taxonomy_Guide.docx
├── src/         # corpus generator and gold-set sampler
├── data/        # synthetic corpus; sealed/ holds the answer key (Week 3)
├── eval/        # gold evaluation set
└── weekly/      # weekly logs
```

All data in this repository is synthetic. No personal data is included.
