from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Tuple

from prospector.source_contracts import ProspectingMission

from .contracts import ResearchMission, ResearchMissionContractError


RESEARCH_MISSION_CONTEXT_KEY = "research_mission"


@dataclass(frozen=True, slots=True)
class ProspectingPlan:
    """Technical selectors chosen after a ResearchMission has been admitted."""

    host_tlds: Tuple[str, ...] = ()
    languages: Tuple[str, ...] = ()
    path_terms: Tuple[str, ...] = ()
    media_types: Tuple[str, ...] = ("text/html",)
    max_candidates: int = 500
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "host_tlds", tuple(self.host_tlds or ())
        )
        object.__setattr__(
            self, "languages", tuple(self.languages or ())
        )
        object.__setattr__(
            self, "path_terms", tuple(self.path_terms or ())
        )
        object.__setattr__(
            self, "media_types", tuple(self.media_types or ())
        )
        if not isinstance(self.context, Mapping):
            raise ResearchMissionContractError(
                "prospecting plan context must be a mapping"
            )
        context = dict(self.context)
        if RESEARCH_MISSION_CONTEXT_KEY in context:
            raise ResearchMissionContractError(
                f"{RESEARCH_MISSION_CONTEXT_KEY!r} is reserved "
                "for ResearchMission provenance"
            )
        object.__setattr__(
            self, "context", MappingProxyType(context)
        )


def project_to_prospecting_mission(
    mission: ResearchMission,
    plan: ProspectingPlan,
    *,
    issued_at: datetime,
) -> ProspectingMission:
    """Project research intent into Actor 1's bounded technical contract.

    No selector is inferred from primary_family, subject or questions. The
    caller must provide the technical plan explicitly.
    """

    if not isinstance(mission, ResearchMission):
        raise ResearchMissionContractError(
            "mission must be a ResearchMission"
        )
    if not isinstance(plan, ProspectingPlan):
        raise ResearchMissionContractError(
            "plan must be a ProspectingPlan"
        )
    context = dict(plan.context)
    context[RESEARCH_MISSION_CONTEXT_KEY] = dict(
        mission.to_provenance_payload()
    )
    return ProspectingMission(
        mission_key=mission.mission_ref,
        issued_at=issued_at,
        host_tlds=plan.host_tlds,
        languages=plan.languages,
        path_terms=plan.path_terms,
        media_types=plan.media_types,
        max_candidates=plan.max_candidates,
        context=context,
    )
