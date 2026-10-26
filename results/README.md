# Results

Prediction files from `src/classify_llm.py` (`llm_<prompt>_<input>.csv` + `.json` run log with model, prompt version, tokens and cost) and `src/baseline.py` (`baseline_<method>_<split>.csv`). Score any of them with `src/evaluate.py`; it also writes `*_errors.csv` for error analysis by cause.

The held-out split is run once, with the final prompt only. Its score is the reported result.
