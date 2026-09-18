"""Shared ranking result types and the abstract ranker interface.

Both `TfidfRanker` and `EmbeddingRanker` implement `score_jobs` only; sorting,
deterministic tie-breaking, top-K selection, and structured explanations are
handled once here so the two rankers stay directly comparable.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from swetrack.domains.opportunities.models import CandidateProfile, JobRecord, MatchReasons, RankerName, RecommendationItem

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ScoredJob:
    """One job with its raw similarity score, before sorting or explanation."""

    job: JobRecord
    score: float


def _contains_ci(needle: str, haystack: str) -> bool:
    return bool(needle) and needle.lower() in haystack.lower()


def _matched_skills(profile: CandidateProfile, job: JobRecord) -> list[str]:
    matched: list[str] = []
    for skill in profile.skills:
        if any(_contains_ci(skill, js) or _contains_ci(js, skill) for js in job.skills):
            matched.append(skill)
    return matched


def _role_words(role: str) -> list[str]:
    return [w for w in _WORD_RE.findall(role.lower()) if len(w) > 2]


def _matched_roles(profile: CandidateProfile, job: JobRecord) -> list[str]:
    title_lower = job.title.lower()
    matched: list[str] = []
    for role in profile.preferred_roles:
        words = _role_words(role)
        if words and all(word in title_lower for word in words):
            matched.append(role)
    return matched


def _matched_locations(profile: CandidateProfile, job: JobRecord) -> list[str]:
    matched: list[str] = []
    for location in profile.preferred_locations:
        if _contains_ci(location, job.location) or _contains_ci(job.location, location):
            matched.append(location)
    return matched


def _matched_companies(profile: CandidateProfile, job: JobRecord) -> list[str]:
    matched: list[str] = []
    for company in profile.preferred_companies:
        if _contains_ci(company, job.company) or _contains_ci(job.company, company):
            matched.append(company)
    return matched


def build_match_reasons(profile: CandidateProfile, job: JobRecord) -> MatchReasons:
    """Transparent structured overlap between a profile and a job.

    This is independent of ranker scoring: embedding similarity coordinates
    are never treated as interpretable features.
    """
    return MatchReasons(
        matched_skills=_matched_skills(profile, job),
        matched_roles=_matched_roles(profile, job),
        matched_locations=_matched_locations(profile, job),
        matched_companies=_matched_companies(profile, job),
    )


def build_recommendation_items(
    profile: CandidateProfile,
    scored_jobs: list[ScoredJob],
    ranker_name: RankerName,
    top_k: int,
) -> list[RecommendationItem]:
    """Sort by descending score with stable job-ID tie-breaking, then take top K."""
    ordered = sorted(scored_jobs, key=lambda sj: (-sj.score, sj.job.job_id))
    top = ordered[:top_k]
    items: list[RecommendationItem] = []
    for rank, scored in enumerate(top, start=1):
        reasons = build_match_reasons(profile, scored.job)
        items.append(
            RecommendationItem(
                rank=rank,
                job=scored.job,
                ranker=ranker_name,
                score=scored.score,
                reasons=reasons.as_text(),
            )
        )
    return items


class Ranker(ABC):
    """Common interface implemented by `TfidfRanker` and `EmbeddingRanker`."""

    name: RankerName

    @abstractmethod
    def score_jobs(self, profile: CandidateProfile, jobs: list[JobRecord]) -> list[ScoredJob]:
        """Return one ScoredJob per input job, unsorted and unfiltered."""
        raise NotImplementedError

    def recommend(
        self, profile: CandidateProfile, jobs: list[JobRecord], top_k: int
    ) -> list[RecommendationItem]:
        """Score, sort, tie-break, and truncate to the top-K recommendations."""
        if not jobs:
            raise ValueError("jobs must be a non-empty list")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if top_k > len(jobs):
            raise ValueError(f"top_k={top_k} exceeds available jobs ({len(jobs)})")
        scored = self.score_jobs(profile, jobs)
        return build_recommendation_items(profile, scored, self.name, top_k)
