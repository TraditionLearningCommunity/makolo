from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class CandidateKey:
    """Logical identity of one real Discovery possibility."""

    family: str
    object_id: str

    def __str__(self) -> str:
        return f"{self.family}:{self.object_id}"


def activity_candidate_key(activity_or_id) -> CandidateKey:
    return CandidateKey("activity", str(getattr(activity_or_id, "pk", activity_or_id)))


def occurrence_candidate_key(occurrence_or_id) -> CandidateKey:
    # Kept for occurrence-specific contexts (map markers, actions, operations).
    # Activity-backed Discovery result identity now uses activity_candidate_key.
    return CandidateKey("occurrence", str(getattr(occurrence_or_id, "pk", occurrence_or_id)))


def service_activity_candidate_key(activity_or_id) -> CandidateKey:
    return CandidateKey("service_activity", str(getattr(activity_or_id, "pk", activity_or_id)))


def opportunity_candidate_key(opportunity_or_id) -> CandidateKey:
    return CandidateKey("opportunity", str(getattr(opportunity_or_id, "pk", opportunity_or_id)))


def deduplicate_candidates(rows, *, key):
    seen = set()
    result = []
    for row in rows:
        candidate_key = key(row)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        result.append(row)
    return result
