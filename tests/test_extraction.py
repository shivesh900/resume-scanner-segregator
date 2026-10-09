from pathlib import Path

import pytest

from resume_scanner.extractor import extract_experience_years, extract_profile, split_sections
from resume_scanner.parser import UnsupportedFileError, extract_text
from resume_scanner.skills import expand_implied, find_skills

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data" / "resumes"

RESUME = """JANE DOE
jane.doe@example.com | +91 98765 43210 | github.com/janedoe
Skills
Python, C++, JavaScript, scikit-learn, PyTorch, REST APIs, Docker
Experience
ML Intern - Acme (fictional)   Jan 2022 - Dec 2022
Data Intern - Beta (fictional)   Jun 2022 - Jun 2023
Education
B.Tech Computer Science, 2024
"""


def test_skills_respect_word_boundaries():
    skills = find_skills("I write JavaScript and C++ daily, plus some Java.")
    assert {"JavaScript", "C++", "Java"} <= set(skills)
    assert "Java" not in find_skills("I only write JavaScript")


def test_single_letter_languages_are_not_false_positives():
    assert "R" not in find_skills("Ready to go, a great team player")
    assert "Go" not in find_skills("Let's go build things")


def test_implied_skills():
    assert "Machine Learning" in expand_implied(["PyTorch"])
    assert "Deep Learning" in expand_implied(["PyTorch"])


def test_profile_fields():
    p = extract_profile(RESUME)
    assert p.name == "Jane Doe"
    assert p.email == "jane.doe@example.com"
    assert p.phone and p.phone.replace(" ", "").endswith("9876543210")
    assert "github.com/janedoe" in p.links
    assert p.education == "Bachelor's"
    assert {"Python", "PyTorch", "scikit-learn", "Docker"} <= set(p.skills)


@pytest.mark.parametrize("text,expected", [
    ("B.E. Computer Science, 2021", "Bachelor's"),
    ("B.Tech CSE", "Bachelor's"),
    ("MBA Marketing", "Master's"),
    ("M.Tech AI and B.Tech CSE", "Master's"),
    ("Diploma in Computer Engineering", "Diploma"),
    ("Happy to be here", None),
])
def test_education_levels(text, expected):
    from resume_scanner.extractor import extract_education
    assert extract_education(text) == expected


def test_overlapping_experience_is_merged():
    # Jan 2022 - Jun 2023 merged = 17 months, not 11 + 12 = 23
    assert extract_experience_years(RESUME) == pytest.approx(17 / 12, abs=0.05)


def test_sections_detected():
    assert {"skills", "experience", "education"} <= set(split_sections(RESUME))


@pytest.mark.parametrize("name", ["aarav_mehta.pdf", "priya_raman.docx"])
def test_parse_pdf_and_docx(name):
    text = extract_text(SAMPLES / name)
    assert "@example." in text
    assert "Python" in text


def test_unsupported_file():
    with pytest.raises(UnsupportedFileError):
        extract_text(b"hello", filename="resume.png")
