# Week 3 Log: From Classified Reports to Findings

**Chiyu Xu · Applied AI Analyst Intern · Week 3**

## What was done
- **Rates, not counts.** Every comparison divides incidents by operating hours. The corpus had no exposure data, so I generated operating hours and 3,000 normal-operation telemetry windows after the corpus, from stated assumptions, without touching the reports or the sealed key.
- **Trends and themes** (`src/w03_trends.py`): quasi-Poisson weekly trends per category, each site vs the rest of the fleet, cold vs warm battery incidents, and keyword themes in Fari complaints before and after the 1 April update.
- **Hotspots** (`src/w03_hotspots.py`): rate per zone vs fleet with an exact test and Benjamini-Hochberg correction, plus Getis-Ord Gi* on a 500 m distance band.
- **Telemetry** (`src/w03_telemetry.py`): pre-incident vs normal hours with 95% CIs and effect sizes, and a 5-fold cross-validated logistic regression.
- **Answer key** (`src/w03_answer_key.py`): opened only after the analyses were final; sha256 matched the value published in Week 1.

## Results
- Below 0 °C the battery-incident rate is **1.8×** the warm rate (95% CI 1.32–2.45).
- Fari response-delay complaints rose **5×** per active hour after 1 April (CI 2.8–9.1); latency 1.75 s → 3.04 s.
- Rising motor current in the hour before a **sensor** fault separates those hours from normal ones (AUC 0.996). Most software, access and human categories leave no telemetry trace (AUC ≈ 0.5).
- Site_C North has the fleet's highest navigation-incident rate (2.1×), but it **does not survive** correction for 25 zones (q = 0.33).
- Answer key: **3 of 4 planted patterns found, 1 partial** (Site_C North). With the true labels it is still not significant, so the miss comes from sample size, not the classifier. The classifier agreed with the generator labels on 96.9% of all 2,000 reports.

## What I learned
- **Multiple testing matters in practice.** 15 zone-category cells passed p < 0.05, which is about what 350 tests give by chance alone. Without correction I would have reported a dozen false hotspots.
- **Gi* needs enough neighbours.** With 25 zones and 1–4 neighbours each, the permutation p-values were unstable, so I used Gi* as context and a rate test as the main evidence.
- **High AUC can just restate the label.** Low battery predicts a battery incident because the label is defined that way. The useful signal is the non-obvious one: drive current before a sensor fault.
- **Severity was never recoverable from the text.** The generator drew severity independently of the text, which explains part of the weak severity agreement in Week 2.

## Next
- Week 4: governance and handover documents.
- Fix the taxonomy rule for weather-rule pauses (E1, not NO_INCIDENT), the classifier's largest error.
- Public review snippets were not collected; add them if time allows.
