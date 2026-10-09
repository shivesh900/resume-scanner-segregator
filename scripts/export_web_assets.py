"""Export the Python taxonomy/config to JSON for the in-browser engine (frontend/src/engine).

The browser demo on GitHub Pages runs a JavaScript port of resume_scanner. This
script keeps both in sync: the skills taxonomy, implications, section headings
and scikit-learn's English stop-word list are generated from the Python source
of truth. CI runs it and fails if the committed JSON is stale.

Run:  python scripts/export_web_assets.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # noqa: E402

from resume_scanner import extractor, skills  # noqa: E402
from resume_scanner.matcher import Weights  # noqa: E402
from resume_scanner.segregator import Thresholds  # noqa: E402

OUT = ROOT / "frontend" / "src" / "engine" / "config.json"
PUBLIC = ROOT / "frontend" / "public" / "samples"


def main():
    cfg = {
        "skills": skills.SKILLS,
        "implies": skills.IMPLIES,
        "ambiguous": sorted(skills._AMBIGUOUS),
        "no_canonical_match": sorted(skills._NO_CANONICAL_MATCH),
        "section_headings": extractor.SECTION_HEADINGS,
        "stop_words": sorted(ENGLISH_STOP_WORDS),
        "weights": Weights().__dict__,
        "thresholds": {"high": Thresholds().high, "medium": Thresholds().medium},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cfg, indent=1, sort_keys=True) + "\n")
    # sample data for the "Load demo data" button in the static build
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / "sample_data" / "resumes").iterdir():
        shutil.copy(p, PUBLIC / p.name)
    shutil.copy(ROOT / "sample_data" / "job_descriptions" / "ml_engineer.txt", PUBLIC / "ml_engineer.txt")
    names = sorted(p.name for p in (ROOT / "sample_data" / "resumes").iterdir())
    (PUBLIC / "index.json").write_text(json.dumps(names, indent=1) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)} and {len(names)} samples to {PUBLIC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
