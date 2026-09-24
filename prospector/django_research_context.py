from __future__ import annotations

from collections import OrderedDict
from typing import Mapping, Tuple

from research_missions.contracts import (
    ResearchContext,
    ResearchMission,
    ResearchMissionContractError,
)
from research_missions.prospecting import RESEARCH_MISSION_CONTEXT_KEY

from .django_app.models import ProspectorFrontierEvidence


class DjangoProspectorResearchContextSource:
    """Read model over durable Prospecteur evidence for future Actor 3 use."""

    def contexts_for_target(
        self,
        target_key: str,
    ) -> Tuple[ResearchContext, ...]:
        if not isinstance(target_key, str) or not target_key.strip():
            raise ResearchMissionContractError(
                "target_key must not be empty"
            )
        target_key = target_key.strip()
        rows = ProspectorFrontierEvidence.objects.filter(
            frontier_entry__target_key=target_key
        ).order_by("last_discovered_at", "id")

        merged = OrderedDict()
        for row in rows:
            policy_context = row.policy_context
            if not isinstance(policy_context, Mapping):
                continue
            mission_context = policy_context.get("mission_context")
            if not isinstance(mission_context, Mapping):
                continue
            payload = mission_context.get(
                RESEARCH_MISSION_CONTEXT_KEY
            )
            if not isinstance(payload, Mapping):
                continue
            try:
                mission = ResearchMission.from_provenance_payload(
                    payload
                )
            except ResearchMissionContractError:
                # Malformed provenance never becomes Actor 3 context.
                # The original evidence remains durable for audit.
                continue
            current = ResearchContext.from_mission(mission)
            previous = merged.get(current.mission_ref)
            if previous is not None:
                current = current.with_merged_provenance(previous)
            merged[current.mission_ref] = current

        return tuple(merged[key] for key in sorted(merged))
