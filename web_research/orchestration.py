from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .contracts import WebResearchContractError
from .deepen import DeepenOutput
from .discovery import DiscoveryKnowledgeState, DiscoveryOutput
from .watch import WatchFreshnessState, WatchOutput


CYCLE_PLAN_CONTRACT_VERSION = 1


class CycleActionKind(str, Enum):
    DEEPEN_MISSION = "deepen_mission"
    OBSERVE_SOURCE = "observe_source"
    WATCH_SOURCE = "watch_source"
    HOLD_FOR_RESOLUTION = "hold_for_resolution"
    NO_ACTION = "no_action"


@dataclass(frozen=True, slots=True)
class CycleAction:
    action_kind: CycleActionKind
    candidate_ref: str | None = None
    source_ref: str | None = None
    mission_ref: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind = CycleActionKind(self.action_kind)
        object.__setattr__(self, "action_kind", kind)

        candidate_ref = (self.candidate_ref or "").strip() or None
        source_ref = (self.source_ref or "").strip() or None
        mission_ref = (self.mission_ref or "").strip() or None
        object.__setattr__(self, "candidate_ref", candidate_ref)
        object.__setattr__(self, "source_ref", source_ref)
        object.__setattr__(self, "mission_ref", mission_ref)

        normalized = []
        for value in tuple(self.reason_codes or ()):
            value = str(value).strip().lower()
            if (
                not value
                or not value[0].isalpha()
                or any(
                    char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
                    for char in value
                )
            ):
                raise WebResearchContractError(
                    "cycle action reason_codes must contain stable technical codes"
                )
            if value not in normalized:
                normalized.append(value)
        object.__setattr__(self, "reason_codes", tuple(normalized))

        if kind is CycleActionKind.DEEPEN_MISSION:
            if candidate_ref is None or mission_ref is None:
                raise WebResearchContractError(
                    "deepen_mission requires candidate_ref and mission_ref"
                )
            if source_ref is not None:
                raise WebResearchContractError(
                    "deepen_mission cannot carry source_ref"
                )
        elif kind in {
            CycleActionKind.OBSERVE_SOURCE,
            CycleActionKind.WATCH_SOURCE,
        }:
            if source_ref is None:
                raise WebResearchContractError(
                    f"{kind.value} requires source_ref"
                )
            if mission_ref is not None:
                raise WebResearchContractError(
                    f"{kind.value} cannot carry mission_ref"
                )
        elif kind is CycleActionKind.HOLD_FOR_RESOLUTION:
            if candidate_ref is None:
                raise WebResearchContractError(
                    "hold_for_resolution requires candidate_ref"
                )
            if source_ref is not None or mission_ref is not None:
                raise WebResearchContractError(
                    "hold_for_resolution carries only candidate_ref"
                )
        elif kind is CycleActionKind.NO_ACTION:
            if mission_ref is not None:
                raise WebResearchContractError(
                    "no_action cannot carry mission_ref"
                )

    def to_payload(self):
        return {
            "action_kind": self.action_kind.value,
            "candidate_ref": self.candidate_ref,
            "source_ref": self.source_ref,
            "mission_ref": self.mission_ref,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class CyclePlan:
    """Standard read-only execution plan for the next Makolo research step."""

    discovery_request_ref: str
    generated_at: datetime
    actions: tuple[CycleAction, ...] = ()
    contract_version: int = CYCLE_PLAN_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.discovery_request_ref:
            raise WebResearchContractError(
                "cycle plan requires discovery_request_ref"
            )
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise WebResearchContractError(
                "cycle plan generated_at must be timezone-aware"
            )
        object.__setattr__(
            self,
            "generated_at",
            self.generated_at.astimezone(timezone.utc),
        )
        actions = tuple(self.actions)
        if any(not isinstance(item, CycleAction) for item in actions):
            raise WebResearchContractError(
                "cycle plan actions must contain CycleAction"
            )
        object.__setattr__(self, "actions", actions)
        if self.contract_version != CYCLE_PLAN_CONTRACT_VERSION:
            raise WebResearchContractError(
                "unsupported cycle plan contract version"
            )

    @property
    def counts_by_action(self) -> dict[str, int]:
        counts = {kind.value: 0 for kind in CycleActionKind}
        for action in self.actions:
            counts[action.action_kind.value] += 1
        return counts

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "discovery_request_ref": self.discovery_request_ref,
            "generated_at": self.generated_at.isoformat(),
            "action_count": len(self.actions),
            "counts_by_action": self.counts_by_action,
            "actions": [item.to_payload() for item in self.actions],
        }


class CyclePlanner:
    """Combine standard outputs into explicit next-step decisions.

    This planner never executes actions. It exists to keep one deterministic,
    auditable decision layer between research outputs and Actor/runtime workers.
    """

    def plan(
        self,
        *,
        discovery: DiscoveryOutput,
        deepen: DeepenOutput,
        watch: WatchOutput,
        generated_at: datetime,
    ) -> CyclePlan:
        if not isinstance(discovery, DiscoveryOutput):
            raise WebResearchContractError(
                "discovery must be a DiscoveryOutput"
            )
        if not isinstance(deepen, DeepenOutput):
            raise WebResearchContractError(
                "deepen must be a DeepenOutput"
            )
        if not isinstance(watch, WatchOutput):
            raise WebResearchContractError(
                "watch must be a WatchOutput"
            )
        if deepen.discovery_request_ref != discovery.request_ref:
            raise WebResearchContractError(
                "deepen output does not belong to discovery output"
            )
        if watch.discovery_request_ref != discovery.request_ref:
            raise WebResearchContractError(
                "watch output does not belong to discovery output"
            )

        suggestions_by_candidate = {}
        for suggestion in deepen.suggestions:
            suggestions_by_candidate.setdefault(
                suggestion.candidate_ref,
                [],
            ).append(suggestion)

        watch_by_source = {
            target.source_ref: target
            for target in watch.targets
        }
        actions = []
        action_keys = set()

        def add(action: CycleAction):
            key = (
                action.action_kind.value,
                action.candidate_ref,
                action.source_ref,
                action.mission_ref,
            )
            if key not in action_keys:
                action_keys.add(key)
                actions.append(action)

        for record in discovery.records:
            for suggestion in suggestions_by_candidate.get(
                record.candidate_ref,
                (),
            ):
                add(
                    CycleAction(
                        action_kind=CycleActionKind.DEEPEN_MISSION,
                        candidate_ref=record.candidate_ref,
                        mission_ref=suggestion.mission_ref,
                        reason_codes=("family_coverage_incomplete",),
                    )
                )

            for source_ref in record.source_refs:
                watch_target = watch_by_source.get(source_ref)
                if watch_target is None:
                    add(
                        CycleAction(
                            action_kind=CycleActionKind.OBSERVE_SOURCE,
                            candidate_ref=record.candidate_ref,
                            source_ref=source_ref,
                            reason_codes=("watch_state_unavailable",),
                        )
                    )
                    continue

                if watch_target.freshness_state is WatchFreshnessState.DUE:
                    add(
                        CycleAction(
                            action_kind=CycleActionKind.WATCH_SOURCE,
                            candidate_ref=record.candidate_ref,
                            source_ref=source_ref,
                            reason_codes=("freshness_due",),
                        )
                    )
                elif (
                    watch_target.freshness_state
                    is WatchFreshnessState.UNRESOLVED
                ):
                    add(
                        CycleAction(
                            action_kind=CycleActionKind.OBSERVE_SOURCE,
                            candidate_ref=record.candidate_ref,
                            source_ref=source_ref,
                            reason_codes=("source_not_yet_watchable",),
                        )
                    )

            if (
                record.knowledge_state
                in {
                    DiscoveryKnowledgeState.AMBIGUOUS,
                    DiscoveryKnowledgeState.UNRESOLVED,
                }
                and not suggestions_by_candidate.get(record.candidate_ref)
            ):
                add(
                    CycleAction(
                        action_kind=CycleActionKind.HOLD_FOR_RESOLUTION,
                        candidate_ref=record.candidate_ref,
                        reason_codes=("identity_not_resolved",),
                    )
                )

            if (
                record.knowledge_state is DiscoveryKnowledgeState.KNOWN
                and not suggestions_by_candidate.get(record.candidate_ref)
                and all(
                    watch_by_source.get(source_ref) is not None
                    and watch_by_source[source_ref].freshness_state
                    is WatchFreshnessState.FRESH
                    for source_ref in record.source_refs
                )
            ):
                add(
                    CycleAction(
                        action_kind=CycleActionKind.NO_ACTION,
                        candidate_ref=record.candidate_ref,
                        reason_codes=("known_complete_and_fresh",),
                    )
                )

        return CyclePlan(
            discovery_request_ref=discovery.request_ref,
            generated_at=generated_at,
            actions=tuple(actions),
        )
