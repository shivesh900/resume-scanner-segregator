"""Command-line screening.

Example:
    python -m resume_scanner.cli --jd sample_data/job_descriptions/ml_engineer.txt sample_data/resumes/*
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .parser import SUPPORTED_EXTENSIONS
from .pipeline import screen_files
from .segregator import PRIORITIES, Thresholds

COLORS = {"High": "\033[92m", "Medium": "\033[93m", "Low": "\033[91m"}
RESET = "\033[0m"


def _expand(paths):
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.suffix.lower() in SUPPORTED_EXTENSIONS)
        elif p.suffix.lower() in SUPPORTED_EXTENSIONS:
            out.append(p)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Screen resumes against a job description.")
    ap.add_argument("resumes", nargs="+", help="resume files (PDF/DOCX/TXT) or folders")
    ap.add_argument("--jd", required=True, help="job description text file (first line = title)")
    ap.add_argument("--high", type=float, default=70.0, help="score threshold for High priority")
    ap.add_argument("--medium", type=float, default=45.0, help="score threshold for Medium priority")
    ap.add_argument("--csv", help="write ranked results to this CSV file")
    ap.add_argument("--json", action="store_true", help="print full JSON instead of a table")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)

    lines = Path(args.jd).read_text().splitlines()
    title, text = lines[0].strip(), "\n".join(lines[1:])
    files = _expand(args.resumes)
    if not files:
        print("No PDF/DOCX/TXT resumes found.", file=sys.stderr)
        return 1
    job, results = screen_files(title, text, files, Thresholds(args.high, args.medium))

    if args.json:
        print(json.dumps({"job": job.to_dict(), "candidates": results}, indent=2))
    else:
        c = (lambda p: "") if args.no_color else (lambda p: COLORS[p])
        r = "" if args.no_color else RESET
        print(f"\nJob: {job.title}")
        print(f"Required: {', '.join(job.required_skills) or '-'}")
        print(f"Preferred: {', '.join(job.preferred_skills) or '-'} | Min experience: {job.min_years:g} yrs\n")
        print(f"{'#':>2}  {'Candidate':<22} {'Score':>5}  {'Priority':<8} {'Exp':>4}  Missing required skills")
        print("-" * 86)
        for i, x in enumerate(results, 1):
            missing = ", ".join(x["missing_required"][:4]) + (" ..." if len(x["missing_required"]) > 4 else "")
            print(f"{i:>2}  {x['name'][:22]:<22} {x['score']:>5.1f}  {c(x['priority'])}{x['priority']:<8}{r} "
                  f"{x['experience_years']:>4.1f}  {missing or '-'}")
        counts = {p: sum(1 for x in results if x["priority"] == p) for p in PRIORITIES}
        avg_ms = sum(x["processing_ms"] for x in results) / len(results)
        print(f"\n{len(results)} resumes | High {counts['High']} | Medium {counts['Medium']} | "
              f"Low {counts['Low']} | avg {avg_ms:.0f} ms per resume\n")

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["rank", "name", "email", "score", "priority", "experience_years",
                        "matched_required", "missing_required", "filename"])
            for i, x in enumerate(results, 1):
                w.writerow([i, x["name"], x["email"], x["score"], x["priority"], x["experience_years"],
                            "; ".join(x["matched_required"]), "; ".join(x["missing_required"]), x["filename"]])
        print(f"Saved {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
