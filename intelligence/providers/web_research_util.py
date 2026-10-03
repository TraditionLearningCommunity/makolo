from __future__ import annotations

from typing import Mapping

from intelligence.exceptions import InvalidProviderResult


def web_research_payload(request):
    value = request.input.get("request")
    if not isinstance(value, Mapping):
        raise InvalidProviderResult("web_research_input_invalid")
    mission = value.get("mission")
    if not isinstance(mission, Mapping):
        raise InvalidProviderResult("web_research_mission_invalid")
    subject = mission.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidProviderResult("web_research_subject_invalid")
    return mission


def mission_query(mission: Mapping) -> str:
    values = [mission.get("subject")]
    values.extend(mission.get("questions") or ())
    values.extend(mission.get("unknowns") or ())
    parts = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = " ".join(value.split())
        if normalized and normalized not in parts:
            parts.append(normalized)
    if not parts:
        raise InvalidProviderResult("web_research_query_empty")
    return "\n".join(parts)


def mission_candidate_limit(
    mission: Mapping,
    *,
    default: int = 10,
    maximum: int | None = None,
) -> int:
    limits = mission.get("limits")
    raw = limits.get("max_candidates") if isinstance(limits, Mapping) else None
    value = raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else default
    if maximum is not None:
        value = min(value, maximum)
    return max(value, 1)


def normalized_text(value, *, limit: int = 4000) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]
