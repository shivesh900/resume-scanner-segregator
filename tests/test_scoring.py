import pytest

from resume_scanner.extractor import extract_profile
from resume_scanner.matcher import parse_job, score_candidate
from resume_scanner.segregator import Thresholds, priority_for, segregate

JD = """Requirements
- 2+ years of experience
- Python, SQL, scikit-learn, PyTorch
Nice to have
- Docker, AWS
"""

STRONG = """ASHA KUMAR
asha@example.com
Skills
Python, SQL, scikit-learn, PyTorch, Docker, AWS
Experience
ML Engineer - Demo Co   Jan 2020 - Jan 2023
"""
WEAK = """RAVI PATEL
ravi@example.com
Skills
Figma, Photoshop, Communication
"""


def test_job_parsing_splits_required_and_preferred():
    job = parse_job("ML Engineer", JD)
    assert set(job.required_skills) >= {"Python", "SQL", "scikit-learn", "PyTorch"}
    assert set(job.preferred_skills) == {"Docker", "AWS"}
    assert job.min_years == 2


def test_strong_candidate_outscores_weak():
    job = parse_job("ML Engineer", JD)
    strong = score_candidate(job, extract_profile(STRONG), STRONG)
    weak = score_candidate(job, extract_profile(WEAK), WEAK)
    assert strong.score > 70 > weak.score
    assert strong.missing_required == []
    assert "Python" in weak.missing_required
    assert 0 <= weak.score <= 100


@pytest.mark.parametrize("score,expected", [(95, "High"), (70, "High"), (69.9, "Medium"), (45, "Medium"), (10, "Low")])
def test_priority_thresholds(score, expected):
    assert priority_for(score) == expected


def test_segregate_sorts_each_bucket():
    out = segregate([{"score": 50}, {"score": 90}, {"score": 80}, {"score": 5}])
    assert [c["score"] for c in out["High"]] == [90, 80]
    assert len(out["Medium"]) == 1 and len(out["Low"]) == 1


def test_invalid_thresholds():
    with pytest.raises(ValueError):
        Thresholds(high=40, medium=60)
