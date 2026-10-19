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
| `data/`: synthetic field-report corpus with planted patterns, public text sample, sealed answer key | In progress |
| `eval/gold_set.csv`: 250 hand-labelled reports, tuning/held-out split, Cohen's kappa | In progress |

### Key taxonomy decisions
1. Classify by **where the robot failed**, not by the trigger; the trigger is recorded in the root-cause flag.
2. Added **S5 AI Detection Error**: sensors and software work, but the AI's judgement is wrong (e.g., Fari false fall alerts).
3. **NO_INCIDENT** covers designed behaviour and safety rules working as intended.
4. Privacy and consent issues are handled as data governance (Data Landscape), not as robot incidents.

## Repository structure
```
├── W01_Data_Landscape.docx
├── W01_Taxonomy_Guide.docx
├── data/        # synthetic corpus (Week 1, in progress)
├── eval/        # gold evaluation set (Week 1, in progress)
└── weekly/      # weekly logs
```

All data in this repository is synthetic. No personal data is included.
