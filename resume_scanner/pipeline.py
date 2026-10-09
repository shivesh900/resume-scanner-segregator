"""End-to-end screening: file -> text -> profile -> score -> priority."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from .extractor import extract_profile
from .matcher import JobProfile, Weights, parse_job, score_candidate
from .parser import extract_text
from .segregator import Thresholds, priority_for


def screen_resume(job: JobProfile, data: Union[bytes, str, Path], filename: Optional[str] = None,
                  weights: Optional[Weights] = None, thresholds: Thresholds = Thresholds()) -> dict:
    started = time.perf_counter()
    filename = filename or Path(str(data)).name
    text = extract_text(data, filename=filename)
    profile = extract_profile(text)
    match = score_candidate(job, profile, text, weights)
    return {
        "filename": filename,
        "name": profile.name or Path(filename).stem.replace("_", " ").title(),
        "email": profile.email,
        "phone": profile.phone,
        "links": profile.links,
        "education": profile.education,
        "experience_years": profile.experience_years,
        "skills": profile.skills,
        "skills_by_category": profile.skills_by_category,
        "score": match.score,
        "priority": priority_for(match.score, thresholds),
        "components": match.components,
        "matched_required": match.matched_required,
        "missing_required": match.missing_required,
        "matched_preferred": match.matched_preferred,
        "extra_skills": match.extra_skills,
        "processing_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def screen_files(job_title: str, job_text: str, paths: Iterable[Union[str, Path]],
                 thresholds: Thresholds = Thresholds()) -> Tuple[JobProfile, List[dict]]:
    job = parse_job(job_title, job_text)
    results = [screen_resume(job, Path(p), Path(p).name, thresholds=thresholds) for p in paths]
    results.sort(key=lambda r: r["score"], reverse=True)
    return job, results
