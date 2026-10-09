"""Bucket candidates into High / Medium / Low priority from their match score."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

PRIORITIES = ("High", "Medium", "Low")


@dataclass(frozen=True)
class Thresholds:
    high: float = 70.0
    medium: float = 45.0

    def __post_init__(self):
        if not 0 <= self.medium <= self.high <= 100:
            raise ValueError("thresholds must satisfy 0 <= medium <= high <= 100")


def priority_for(score: float, thresholds: Thresholds = Thresholds()) -> str:
    if score >= thresholds.high:
        return "High"
    if score >= thresholds.medium:
        return "Medium"
    return "Low"


def segregate(candidates: Iterable[dict], thresholds: Thresholds = Thresholds()) -> Dict[str, List[dict]]:
    """Group candidate dicts (each with a ``score``) into priority buckets, best first."""
    buckets: Dict[str, List[dict]] = {p: [] for p in PRIORITIES}
    for c in candidates:
        buckets[priority_for(c["score"], thresholds)].append(c)
    for p in PRIORITIES:
        buckets[p].sort(key=lambda c: c["score"], reverse=True)
    return buckets
