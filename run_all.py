"""Rebuild everything in this repository with one command.

  python run_all.py           # data -> evaluation -> Week 3 analysis -> reports (about 1 minute)
  python run_all.py --live    # also re-run LLM classification with `claude -p` (hours; uses the
                              # logged-in Claude subscription; see src/classify_llm.py)

Without --live, classification results are read from results/ and
data/classified_corpus.csv, because an LLM run is slow, costs money and is not
bit-for-bit repeatable. The hand-labelled gold set (eval/gold_set.csv) is never
regenerated. The run ends by checking that the regenerated corpus and the sealed
answer key match their published sha256, so any drift in the generator shows up.
"""

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPT = "classify_v1"
SHA256 = {"data/sealed/answer_key.csv":
          "24e41dccba8d5f6436f881c61fc3c2f815f0c67e797a91ad148d06a7a16777d5"}

DATA = [["src/generate_corpus.py", "--n", "2000", "--seed", "42"],
        ["src/generate_exposure.py", "--seed", "2026"]]
LIVE = [["src/classify_llm.py", "--backend", "claude-cli", "--input", "eval/gold_set.csv",
         "--split", "heldout", "--prompt", PROMPT],
        ["src/classify_llm.py", "--backend", "claude-cli", "--input", "data/field_reports.csv",
         "--batch-size", "25", "--save-corpus", "--prompt", PROMPT]]
EVALUATE = [["src/evaluate.py", "--agreement"],
            ["src/baseline.py", "--method", "keyword", "--split", "heldout"],
            ["src/baseline.py", "--method", "tfidf"],
            ["src/evaluate.py", f"results/llm_{PROMPT}_gold_set_heldout.csv", "--split", "heldout"],
            ["src/evaluate.py", "results/baseline_keyword_heldout.csv", "--split", "heldout"],
            ["src/evaluate.py", "results/baseline_tfidf_heldout.csv", "--split", "heldout"],
            ["src/make_eval_report.py", "--prompt", PROMPT]]
ANALYSIS = [["src/w03_trends.py"], ["src/w03_hotspots.py"], ["src/w03_telemetry.py"],
            ["src/w03_answer_key.py"], ["src/make_findings_report.py"],
            ["src/make_governance_pack.py"]]


def run(step):
    start = time.time()
    done = subprocess.run([sys.executable, *step], cwd=ROOT, capture_output=True, text=True)
    status = "ok" if done.returncode == 0 else "FAILED"
    print(f"  {status:<6} {time.time() - start:5.1f}s  {' '.join(step)}")
    if done.returncode:
        sys.exit(done.stdout[-2000:] + done.stderr[-2000:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="re-run LLM classification (slow)")
    args = ap.parse_args()

    stages = [("1. data", DATA)] + ([("2. LLM classification", LIVE)] if args.live else []) + [
        ("3. evaluation (Week 2)", EVALUATE), ("4. analysis and reports (Week 3)", ANALYSIS)]
    for name, steps in stages:
        print(name)
        for step in steps:
            run(step)

    for path, expected in SHA256.items():
        got = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        print(f"sha256 {path}: {'matches' if got == expected else 'CHANGED ' + got}")
    print("done: see W02_Evaluation_Report.docx, W03_Findings_Report.docx, maps/, figures/")


if __name__ == "__main__":
    main()
