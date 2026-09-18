from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from .errors import ProspectorContractError
from .runtime import RuntimeCycleStats
from .source_contracts import ProspectingMission, SourceRunResult


def _positive_int(name: str, value: int, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProspectorContractError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ProspectorContractError(f"{name} must be a {qualifier} integer")
    return value


def _frozen_counts(name: str, value: Mapping[str, int]) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise ProspectorContractError(f"{name} must be a mapping")
    normalized = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ProspectorContractError(f"{name} keys must be non-empty strings")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ProspectorContractError(f"{name} counts must be non-negative integers")
        normalized[key.strip()] = count
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class PilotPolicy:
    max_source_passes: int
    max_runtime_cycles: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_source_passes",
            _positive_int("max_source_passes", self.max_source_passes),
        )
        object.__setattr__(
            self,
            "max_runtime_cycles",
            _positive_int(
                "max_runtime_cycles",
                self.max_runtime_cycles,
                allow_zero=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class PilotSnapshot:
    entry_count: int = 0
    discovery_count: int = 0
    evidence_count: int = 0
    feedback_events: int = 0
    statuses: Mapping[str, int] = field(default_factory=dict)
    suppression_reasons: Mapping[str, int] = field(default_factory=dict)
    feedback_signals: Mapping[str, int] = field(default_factory=dict)
    evidence_methods: Mapping[str, int] = field(default_factory=dict)
    providers: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("entry_count", "discovery_count", "evidence_count", "feedback_events"):
            object.__setattr__(self, name, _positive_int(name, getattr(self, name), allow_zero=True))
        for name in (
            "statuses",
            "suppression_reasons",
            "feedback_signals",
            "evidence_methods",
            "providers",
        ):
            object.__setattr__(self, name, _frozen_counts(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class PilotRunStats:
    source_passes: int
    source_received: int
    source_admitted: int
    source_exhausted: bool
    source_revision: str
    runtime_cycles: int
    runtime: RuntimeCycleStats

    def __post_init__(self) -> None:
        for name in ("source_passes", "source_received", "source_admitted", "runtime_cycles"):
            object.__setattr__(self, name, _positive_int(name, getattr(self, name), allow_zero=True))
        if not isinstance(self.source_exhausted, bool):
            raise ProspectorContractError("source_exhausted must be a boolean")
        if not isinstance(self.source_revision, str):
            raise ProspectorContractError("source_revision must be a string")
        if not isinstance(self.runtime, RuntimeCycleStats):
            raise ProspectorContractError("runtime must be RuntimeCycleStats")


class ProspectorPilotRunner:
    """Bounded PX8 runner.

    Source discovery is always bounded by the mission and max_source_passes.
    Runtime execution is optional because the Observer-owned RequestQueue is a
    deployment dependency that PX8 must not invent.
    """

    def __init__(self, *, source_runner, runtime=None) -> None:
        self.source_runner = source_runner
        self.runtime = runtime

    async def run(
        self,
        *,
        source,
        mission: ProspectingMission,
        policy: PilotPolicy,
    ) -> PilotRunStats:
        if not isinstance(mission, ProspectingMission):
            raise ProspectorContractError("mission must be ProspectingMission")
        if not isinstance(policy, PilotPolicy):
            raise ProspectorContractError("policy must be PilotPolicy")
        if self.runtime is None and policy.max_runtime_cycles:
            raise ProspectorContractError(
                "runtime cycles requested without an injected Observer runtime"
            )

        source_results: list[SourceRunResult] = []
        for _ in range(policy.max_source_passes):
            result = await self.source_runner.run(
                source=source,
                mission=mission,
            )
            source_results.append(result)
            if result.exhausted:
                break

        runtime_stats = RuntimeCycleStats()
        runtime_cycles = 0
        if self.runtime is not None:
            for _ in range(policy.max_runtime_cycles):
                cycle = await self.runtime.run_cycle()
                runtime_cycles += 1
                runtime_stats = RuntimeCycleStats(
                    claimed=runtime_stats.claimed + cycle.claimed,
                    completed=runtime_stats.completed + cycle.completed,
                    deferred=runtime_stats.deferred + cycle.deferred,
                    suppressed=runtime_stats.suppressed + cycle.suppressed,
                    handoff_errors=runtime_stats.handoff_errors + cycle.handoff_errors,
                    backpressure_released=(
                        runtime_stats.backpressure_released
                        + cycle.backpressure_released
                    ),
                )
                if cycle.claimed == 0:
                    break

        last = source_results[-1] if source_results else None
        return PilotRunStats(
            source_passes=len(source_results),
            source_received=sum(item.received for item in source_results),
            source_admitted=sum(item.admitted for item in source_results),
            source_exhausted=bool(last and last.exhausted),
            source_revision=last.source_revision if last else "",
            runtime_cycles=runtime_cycles,
            runtime=runtime_stats,
        )


def _delta_counts(after: Mapping[str, int], before: Mapping[str, int]) -> dict[str, int]:
    keys = set(after) | set(before)
    return {
        key: after.get(key, 0) - before.get(key, 0)
        for key in sorted(keys)
        if after.get(key, 0) - before.get(key, 0)
    }


def _ratio(numerator: int, denominator: int) -> Mapping[str, Optional[int]]:
    return {
        "numerator": numerator,
        "denominator": denominator if denominator else None,
    }


def build_pilot_scorecard(
    *,
    mission: ProspectingMission,
    policy: PilotPolicy,
    run: PilotRunStats,
    before: PilotSnapshot,
    after: PilotSnapshot,
    started_at: datetime,
    finished_at: datetime,
) -> dict:
    for name, value in (("started_at", started_at), ("finished_at", finished_at)):
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ProspectorContractError(f"{name} must be timezone-aware")
    new_to_mission = after.entry_count - before.entry_count
    discovery_delta = after.discovery_count - before.discovery_count
    evidence_delta = after.evidence_count - before.evidence_count
    evidence_replays = max(discovery_delta - max(evidence_delta, 0), 0)
    feedback_delta = after.feedback_events - before.feedback_events

    scorecard = {
        "contract_version": 1,
        "kind": "prospector_px8_pilot",
        "mission": {
            "mission_key": mission.mission_key,
            "mission_fingerprint": mission.fingerprint,
            "host_tlds": list(mission.host_tlds),
            "languages": list(mission.languages),
            "path_terms": list(mission.path_terms),
            "media_types": list(mission.media_types),
            "max_candidates_per_source_pass": mission.max_candidates,
        },
        "bounds": {
            "max_source_passes": policy.max_source_passes,
            "max_runtime_cycles": policy.max_runtime_cycles,
        },
        "window": {
            "started_at": started_at.astimezone(timezone.utc).isoformat(),
            "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        },
        "source": {
            "passes": run.source_passes,
            "revision": run.source_revision,
            "received": run.source_received,
            "admitted_attempts": run.source_admitted,
            "exhausted": run.source_exhausted,
        },
        "frontier": {
            "new_to_mission_targets": new_to_mission,
            "new_mission_evidence": evidence_delta,
            "evidence_replays": evidence_replays,
            "mission_target_count_after": after.entry_count,
            "status_counts_after": dict(after.statuses),
            "suppression_reasons_after": dict(after.suppression_reasons),
            "evidence_methods_after": dict(after.evidence_methods),
            "providers_after": dict(after.providers),
        },
        "runtime": {
            "configured": policy.max_runtime_cycles > 0,
            "cycles": run.runtime_cycles,
            "claimed": run.runtime.claimed,
            "handoff_accepted": run.runtime.completed,
            "deferred": run.runtime.deferred,
            "suppressed": run.runtime.suppressed,
            "handoff_errors": run.runtime.handoff_errors,
            "backpressure_released": run.runtime.backpressure_released,
        },
        "feedback": {
            "events_delta": feedback_delta,
            "signals_delta": _delta_counts(
                after.feedback_signals,
                before.feedback_signals,
            ),
            "downstream_evaluable": feedback_delta > 0,
        },
        "ratios": {
            "new_to_mission_targets_per_admission_attempt": _ratio(
                max(new_to_mission, 0),
                run.source_admitted,
            ),
            "handoff_acceptance": _ratio(
                run.runtime.completed,
                run.runtime.claimed,
            ),
        },
        "limitations": [],
    }
    if policy.max_runtime_cycles == 0:
        scorecard["limitations"].append("observer_runtime_not_run")
    if feedback_delta <= 0:
        scorecard["limitations"].append("downstream_feedback_not_observed")
    # Verify JSON safety now rather than when an operator writes the report.
    json.dumps(scorecard, ensure_ascii=False, allow_nan=False, sort_keys=True)
    return scorecard
