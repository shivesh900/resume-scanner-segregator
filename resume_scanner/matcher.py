"""Score a candidate profile against a job description.

score = 100 * ( 0.50 * required-skill coverage
              + 0.15 * preferred-skill coverage
              + 0.20 * text similarity (TF-IDF cosine, JD vs resume)
              + 0.15 * experience fit )

Weights live in ``Weights`` and can be tuned per role. Every component is
returned so a recruiter can see *why* a candidate landed in a bucket.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .extractor import CandidateProfile
from .skills import expand_implied, find_skills

_PREFERRED_HEAD = re.compile(
    r"^\s*(nice[ -]to[ -]have|preferred|good to have|bonus|plus|desirable)\b.*$", re.I | re.M
)
_MIN_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)", re.I)


@dataclass
class Weights:
    required: float = 0.50
    preferred: float = 0.15
    similarity: float = 0.20
    experience: float = 0.15


@dataclass
class JobProfile:
    title: str
    text: str
    required_skills: List[str]
    preferred_skills: List[str]
    min_years: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    score: float
    components: Dict[str, float]
    matched_required: List[str]
    missing_required: List[str]
    matched_preferred: List[str]
    extra_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_job(title: str, text: str) -> JobProfile:
    """Split a JD into required vs preferred skills and read the minimum experience."""
    head = _PREFERRED_HEAD.search(text)
    required_text, preferred_text = (text[: head.start()], text[head.start():]) if head else (text, "")
    required = find_skills(required_text)
    preferred = [s for s in find_skills(preferred_text) if s not in required]
    years = [int(y) for y in _MIN_YEARS_RE.findall(required_text)]
    return JobProfile(title=title, text=text, required_skills=required,
                      preferred_skills=preferred, min_years=float(min(years)) if years else 0.0)


def text_similarity(job_text: str, resume_text: str) -> float:
    """TF-IDF cosine similarity (unigrams + bigrams, English stop words removed)."""
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    try:
        m = vec.fit_transform([job_text, resume_text])
    except ValueError:  # empty vocabulary
        return 0.0
    return float(cosine_similarity(m[0], m[1])[0, 0])


def score_candidate(job: JobProfile, profile: CandidateProfile, resume_text: str,
                    weights: Optional[Weights] = None) -> MatchResult:
    w = weights or Weights()
    have = set(expand_implied(profile.skills))
    matched_req = [s for s in job.required_skills if s in have]
    missing_req = [s for s in job.required_skills if s not in have]
    matched_pref = [s for s in job.preferred_skills if s in have]

    req_cov = len(matched_req) / len(job.required_skills) if job.required_skills else 1.0
    pref_cov = len(matched_pref) / len(job.preferred_skills) if job.preferred_skills else 0.0
    # raw TF-IDF cosine between a JD and a resume rarely exceeds ~0.5; rescale to 0..1
    sim = min(1.0, text_similarity(job.text, resume_text) / 0.5)
    exp = 1.0 if job.min_years <= 0 else min(1.0, profile.experience_years / job.min_years)

    pref_weight = w.preferred if job.preferred_skills else 0.0
    total_w = w.required + pref_weight + w.similarity + w.experience
    raw = (w.required * req_cov + pref_weight * pref_cov + w.similarity * sim + w.experience * exp) / total_w

    return MatchResult(
        score=round(100 * raw, 1),
        components={
            "required_skills": round(req_cov, 3),
            "preferred_skills": round(pref_cov, 3),
            "text_similarity": round(sim, 3),
            "experience_fit": round(exp, 3),
        },
        matched_required=matched_req,
        missing_required=missing_req,
        matched_preferred=matched_pref,
        extra_skills=sorted(set(profile.skills) - set(job.required_skills) - set(job.preferred_skills)),
    )
