"""A small, editable skills taxonomy.

Each canonical skill maps to the aliases that should count as that skill.
Matching is case-insensitive and respects word boundaries, so "java" does not
match "javascript". Extend this file to adapt the scanner to a new domain.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

SKILLS: Dict[str, Dict[str, List[str]]] = {
    "Programming": {
        "Python": ["python", "python3"],
        "Java": ["java"],
        "C++": ["c++", "cpp"],
        "C#": ["c#", "csharp"],
        "JavaScript": ["javascript", "js", "es6"],
        "TypeScript": ["typescript", "ts"],
        "Go": ["golang"],
        "R": ["r programming", "rstudio"],
        "SQL": ["sql"],
        "Bash": ["bash", "shell scripting"],
    },
    "Machine Learning": {
        "Machine Learning": ["machine learning", "ml"],
        "Deep Learning": ["deep learning", "neural networks", "neural network"],
        "NLP": ["nlp", "natural language processing", "text mining"],
        "Computer Vision": ["computer vision", "image processing", "opencv"],
        "PyTorch": ["pytorch", "torch"],
        "TensorFlow": ["tensorflow", "keras"],
        "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "Transformers": ["transformers", "hugging face", "huggingface", "bert", "llm", "llms"],
        "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "LangChain": ["langchain"],
        "spaCy": ["spacy"],
        "XGBoost": ["xgboost", "lightgbm"],
        "MLOps": ["mlops", "mlflow", "model deployment"],
        "Statistics": ["statistics", "hypothesis testing", "probability"],
        "Data Visualization": ["data visualization", "matplotlib", "seaborn", "plotly"],
        "Power BI": ["power bi", "powerbi"],
        "Tableau": ["tableau"],
    },
    "Web": {
        "React": ["react", "react.js", "reactjs"],
        "Next.js": ["next.js", "nextjs"],
        "Node.js": ["node.js", "nodejs", "node"],
        "Express": ["express", "express.js"],
        "Flask": ["flask"],
        "Django": ["django"],
        "FastAPI": ["fastapi"],
        "REST APIs": ["rest api", "rest apis", "restful", "rest"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3", "tailwind", "tailwind css"],
        "GraphQL": ["graphql"],
    },
    "Data & Cloud": {
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MongoDB": ["mongodb", "mongo"],
        "Redis": ["redis"],
        "Spark": ["spark", "pyspark", "apache spark"],
        "AWS": ["aws", "amazon web services", "ec2", "s3", "sagemaker"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure"],
        "Docker": ["docker", "containers"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Git": ["git", "github", "gitlab"],
        "CI/CD": ["ci/cd", "github actions", "jenkins"],
        "Linux": ["linux", "unix"],
    },
    "Design": {
        "Figma": ["figma"],
        "UI/UX": ["ui/ux", "ux design", "ui design", "user experience", "wireframing", "prototyping"],
        "Adobe XD": ["adobe xd"],
    },
    "Soft Skills": {
        "Communication": ["communication"],
        "Teamwork": ["teamwork", "collaboration"],
        "Leadership": ["leadership", "mentoring"],
        "Problem Solving": ["problem solving", "problem-solving"],
    },
}

# Aliases that are too ambiguous to match on their own in free text.
# Canonical names that are ordinary English words/letters ("R", "Go").
_NO_CANONICAL_MATCH = {"R", "Go"}

_AMBIGUOUS = {"ts", "js", "node", "rest", "ml", "torch", "r programming"}


# Knowing a specialised skill implies the umbrella skill (used for matching only).
IMPLIES: Dict[str, List[str]] = {
    "Deep Learning": ["Machine Learning"],
    "NLP": ["Machine Learning"],
    "Computer Vision": ["Machine Learning"],
    "PyTorch": ["Machine Learning", "Deep Learning"],
    "TensorFlow": ["Machine Learning", "Deep Learning"],
    "scikit-learn": ["Machine Learning"],
    "Transformers": ["NLP"],
    "spaCy": ["NLP"],
    "PostgreSQL": ["SQL"],
    "MySQL": ["SQL"],
    "Next.js": ["React"],
}


def expand_implied(skills: Iterable[str]) -> List[str]:
    """Add umbrella skills implied by specialised ones (PyTorch -> Deep Learning -> ML)."""
    out = set(skills)
    frontier = list(out)
    while frontier:
        for parent in IMPLIES.get(frontier.pop(), []):
            if parent not in out:
                out.add(parent)
                frontier.append(parent)
    return sorted(out)


def all_skills() -> Dict[str, str]:
    """Map canonical skill -> category."""
    return {skill: cat for cat, skills in SKILLS.items() for skill in skills}


@lru_cache(maxsize=1)
def _compiled() -> List[Tuple[str, re.Pattern]]:
    patterns = []
    for skills in SKILLS.values():
        for canonical, aliases in skills.items():
            names = set(aliases)
            if canonical not in _NO_CANONICAL_MATCH:
                names.add(canonical.lower())
            for alias in sorted(names, key=len, reverse=True):
                escaped = re.escape(alias)
                # word boundary that also works for tokens like c++, c#, ci/cd, node.js
                pattern = re.compile(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])", re.IGNORECASE)
                patterns.append((canonical, pattern))
    return patterns


def find_skills(text: str) -> List[str]:
    """Return canonical skills mentioned in ``text`` (sorted, de-duplicated)."""
    found = set()
    for canonical, pattern in _compiled():
        if canonical in found:
            continue
        match = pattern.search(text)
        if not match:
            continue
        alias = match.group(0).lower()
        if alias in _AMBIGUOUS:
            # require the ambiguous alias to appear at least twice or near tech words
            if len(pattern.findall(text)) < 2 and not re.search(
                rf"{re.escape(alias)}\s*(,|/|\||\band\b)", text, re.IGNORECASE
            ):
                continue
        found.add(canonical)
    return sorted(found)


def categorize(skills: Iterable[str]) -> Dict[str, List[str]]:
    lookup = all_skills()
    out: Dict[str, List[str]] = {}
    for s in skills:
        out.setdefault(lookup.get(s, "Other"), []).append(s)
    return out
