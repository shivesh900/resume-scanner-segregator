"""NLP-style information extraction from resume text.

The extractor is deliberately rule-based (regex + a skills taxonomy + section
detection) so that it is fast, explainable and runs without a GPU or API key.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from .skills import categorize, find_skills

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,5}")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(linkedin\.com/in/[\w-]+|github\.com/[\w-]+)", re.I)

SECTION_HEADINGS = {
    "summary": ["summary", "profile", "objective", "about me", "professional summary"],
    "skills": ["skills", "technical skills", "core skills", "key skills", "tech stack"],
    "experience": ["experience", "work experience", "professional experience", "employment", "internships", "internship"],
    "education": ["education", "academics", "academic background", "qualifications"],
    "projects": ["projects", "academic projects", "personal projects", "key projects"],
    "certifications": ["certifications", "certificates", "courses"],
}

_L, _R = r"(?<![a-z])", r"(?![a-z])"
DEGREES = [
    ("PhD", _L + r"(ph\.?d|doctorate)" + _R),
    ("Master's", _L + r"(m\.?tech|m\.e\.?|m\.?sc|mca|mba|m\.?des|master'?s?|m\.s\.)" + _R),
    ("Bachelor's", _L + r"(b\.?tech|b\.e\.?|b\.?sc|bca|b\.?com|b\.?des|bachelor'?s?|b\.s\.|undergraduate)" + _R),
    ("Diploma", _L + r"diploma" + _R),
]
DEGREE_RANK = {"PhD": 4, "Master's": 3, "Bachelor's": 2, "Diploma": 1, None: 0}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_RANGE_RE = re.compile(
    rf"(?:{_MONTH}\s+)?((?:19|20)\d{{2}})\s*(?:-|to|until)\s*(?:(?:{_MONTH}\s+)?((?:19|20)\d{{2}})|(present|current|now|till date))",
    re.I,
)
YEARS_STATED_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+|industry\s+|work\s+)?experience", re.I)


@dataclass
class CandidateProfile:
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    links: List[str]
    skills: List[str]
    skills_by_category: Dict[str, List[str]]
    education: Optional[str]
    experience_years: float
    sections: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("sections", None)
        return d


def split_sections(text: str) -> Dict[str, str]:
    """Split resume text into known sections using heading lines."""
    lookup = {alias: key for key, aliases in SECTION_HEADINGS.items() for alias in aliases}
    sections: Dict[str, List[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        stripped = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if stripped in lookup and len(line.strip()) < 40:
            current = lookup[stripped]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def extract_name(text: str) -> Optional[str]:
    for line in text.splitlines()[:6]:
        line = line.strip()
        if not line or EMAIL_RE.search(line) or any(ch.isdigit() for ch in line):
            continue
        words = line.replace(".", " ").split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() and w.replace("-", "").isalpha() for w in words):
            if line.lower() not in {a for v in SECTION_HEADINGS.values() for a in v}:
                return line.title() if line.isupper() else line
    return None


def extract_phone(text: str) -> Optional[str]:
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13 and not re.fullmatch(r"(19|20)\d{2}(19|20)\d{2}\d*", digits):
            return m.group(0).strip()
    return None


def extract_education(text: str) -> Optional[str]:
    best = None
    for label, pattern in DEGREES:
        if re.search(pattern, text, re.I) and DEGREE_RANK[label] > DEGREE_RANK[best]:
            best = label
    return best


def _months_between(start: Tuple[int, int], end: Tuple[int, int]) -> int:
    return max(0, (end[0] - start[0]) * 12 + (end[1] - start[1]))


def extract_experience_years(text: str, today: Optional[date] = None) -> float:
    """Estimate total experience from date ranges in the experience section.

    Overlapping ranges are merged so concurrent roles are not double counted.
    Falls back to an explicit "N years of experience" statement.
    """
    today = today or date.today()
    sections = split_sections(text)
    scope = sections.get("experience", "")
    intervals = []
    for m in DATE_RANGE_RE.finditer(scope):
        sm, sy, em, ey, present = m.groups()
        start = (int(sy), MONTHS.get((sm or "jan")[:3].lower(), 1))
        if present:
            end = (today.year, today.month)
        else:
            end = (int(ey), MONTHS.get((em or "dec")[:3].lower(), 12))
        if end >= start:
            intervals.append((start, end))
    total = 0
    if intervals:
        intervals.sort()
        merged = [list(intervals[0])]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        total = sum(_months_between(s, e) for s, e in merged)
    years = round(total / 12, 1)
    stated = [float(x) for x in YEARS_STATED_RE.findall(text)]
    if stated:
        years = max(years, max(stated))
    return years


def extract_profile(text: str) -> CandidateProfile:
    sections = split_sections(text)
    skills = find_skills(text)
    links = sorted({m.group(1).lower() for m in URL_RE.finditer(text)})
    email = EMAIL_RE.search(text)
    return CandidateProfile(
        name=extract_name(text),
        email=email.group(0) if email else None,
        phone=extract_phone(sections.get("header", text)),
        links=links,
        skills=skills,
        skills_by_category=categorize(skills),
        education=extract_education(sections.get("education", text)),
        experience_years=extract_experience_years(text),
        sections=sections,
    )
