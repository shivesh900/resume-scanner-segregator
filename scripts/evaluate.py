"""Measure the scanner on the bundled synthetic resumes.

Compares the predicted priority bucket with the hand-assigned
``expected_priority`` in sample_data/labels.csv and reports bucket agreement,
a confusion matrix, rank correlation and throughput.

Run:  python scripts/evaluate.py
"""
from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from resume_scanner.pipeline import screen_files  # noqa: E402
from resume_scanner.segregator import PRIORITIES  # noqa: E402

RANK = {"High": 2, "Medium": 1, "Low": 0}


def main():
    labels = {r["filename"]: r["expected_priority"]
              for r in csv.DictReader(open(ROOT / "sample_data" / "labels.csv"))}
    jd = (ROOT / "sample_data" / "job_descriptions" / "ml_engineer.txt").read_text().splitlines()
    files = [ROOT / "sample_data" / "resumes" / f for f in labels]

    t0 = time.perf_counter()
    _, results = screen_files(jd[0], "\n".join(jd[1:]), files)
    elapsed = time.perf_counter() - t0

    correct = sum(labels[r["filename"]] == r["priority"] for r in results)
    print(f"Resumes: {len(results)}")
    print(f"Bucket agreement with hand labels: {correct}/{len(results)} = {correct / len(results):.0%}")
    print("\nConfusion matrix (rows = expected, cols = predicted)")
    print(f"{'':>8}" + "".join(f"{p:>8}" for p in PRIORITIES))
    for exp in PRIORITIES:
        row = [sum(1 for r in results if labels[r['filename']] == exp and r['priority'] == p) for p in PRIORITIES]
        print(f"{exp:>8}" + "".join(f"{n:>8}" for n in row))
    rho, _ = spearmanr([r["score"] for r in results], [RANK[labels[r["filename"]]] for r in results])
    print(f"\nSpearman rank correlation (score vs expected tier): {rho:.2f}")
    high_scores = [r["score"] for r in results if labels[r["filename"]] == "High"]
    low_scores = [r["score"] for r in results if labels[r["filename"]] == "Low"]
    print(f"Lowest 'High' score {min(high_scores):.1f} vs highest 'Low' score {max(low_scores):.1f}")
    print(f"\nThroughput: {len(results) / elapsed:.1f} resumes/sec "
          f"(median {statistics.median(r['processing_ms'] for r in results):.0f} ms per resume, CPU only)")
    print("\nMisses:")
    for r in results:
        if labels[r["filename"]] != r["priority"]:
            print(f"  {r['name']:<16} expected {labels[r['filename']]:<6} got {r['priority']:<6} (score {r['score']})")


if __name__ == "__main__":
    main()
