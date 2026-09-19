from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .errors import ProspectorContractError


def _non_negative_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProspectorContractError(f"{name} must be a non-negative integer")
    return value


def _optional_non_negative_int(name: str, value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    return _non_negative_int(name, value)


def _aware(name: str, value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _frozen_counts(name: str, value: Mapping[str, int]) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise ProspectorContractError(f"{name} must be a mapping")
    normalized = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ProspectorContractError(f"{name} keys must be non-empty strings")
        normalized[key.strip()] = _non_negative_int(f"{name}[{key!r}]", count)
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    captured_at: datetime
    frontier_total: int
    ready_due: int
    claimed: int
    stale_claims: int
    completed: int
    suppressed: int
    evidence_rows: int
    source_checkpoints: int
    active_source_checkpoints: int
    feedback_events: int
    feedback_projections: int
    feedback_projection_lag_events: int
    expired_budget_counters: int
    expired_budget_reservations: int
    oldest_ready_age_seconds: Optional[int] = None
    oldest_active_checkpoint_age_seconds: Optional[int] = None
    suppression_reasons: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "captured_at", _aware("captured_at", self.captured_at))
        for name in (
            "frontier_total",
            "ready_due",
            "claimed",
            "stale_claims",
            "completed",
            "suppressed",
            "evidence_rows",
            "source_checkpoints",
            "active_source_checkpoints",
            "feedback_events",
            "feedback_projections",
            "feedback_projection_lag_events",
            "expired_budget_counters",
            "expired_budget_reservations",
        ):
            object.__setattr__(
                self,
                name,
                _non_negative_int(name, getattr(self, name)),
            )
        for name in (
            "oldest_ready_age_seconds",
            "oldest_active_checkpoint_age_seconds",
        ):
            value = getattr(self, name)
            object.__setattr__(
                self,
                name,
                _optional_non_negative_int(name, value),
            )
        object.__setattr__(
            self,
            "suppression_reasons",
            _frozen_counts("suppression_reasons", self.suppression_reasons),
        )

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at.isoformat(),
            "frontier": {
                "total": self.frontier_total,
                "ready_due": self.ready_due,
                "claimed": self.claimed,
                "stale_claims": self.stale_claims,
                "completed": self.completed,
                "suppressed": self.suppressed,
                "oldest_ready_age_seconds": self.oldest_ready_age_seconds,
                "suppression_reasons": dict(self.suppression_reasons),
            },
            "provenance": {
                "evidence_rows": self.evidence_rows,
            },
            "sources": {
                "checkpoints": self.source_checkpoints,
                "active_checkpoints": self.active_source_checkpoints,
                "oldest_active_checkpoint_age_seconds": (
                    self.oldest_active_checkpoint_age_seconds
                ),
            },
            "feedback": {
                "events": self.feedback_events,
                "projections": self.feedback_projections,
                "projection_lag_events": self.feedback_projection_lag_events,
            },
            "budgets": {
                "expired_counters": self.expired_budget_counters,
                "expired_reservations": self.expired_budget_reservations,
            },
        }


@dataclass(frozen=True, slots=True)
class OperationsThresholds:
    max_stale_claims: Optional[int] = None
    max_ready_age_seconds: Optional[int] = None
    max_feedback_projection_lag_events: Optional[int] = None
    max_active_checkpoint_age_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        for name in (
            "max_stale_claims",
            "max_ready_age_seconds",
            "max_feedback_projection_lag_events",
            "max_active_checkpoint_age_seconds",
        ):
            object.__setattr__(
                self,
                name,
                _optional_non_negative_int(name, getattr(self, name)),
            )


@dataclass(frozen=True, slots=True)
class OperationsHealth:
    status: str
    failed_checks: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"ok", "degraded"}:
            raise ProspectorContractError("status must be 'ok' or 'degraded'")
        object.__setattr__(self, "failed_checks", tuple(self.failed_checks))
        if self.status == "ok" and self.failed_checks:
            raise ProspectorContractError("ok health cannot contain failed checks")
        if self.status == "degraded" and not self.failed_checks:
            raise ProspectorContractError("degraded health requires failed checks")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "failed_checks": list(self.failed_checks),
        }


def evaluate_operations_health(
    snapshot: OperationsSnapshot,
    thresholds: OperationsThresholds,
) -> OperationsHealth:
    if not isinstance(snapshot, OperationsSnapshot):
        raise ProspectorContractError("snapshot must be OperationsSnapshot")
    if not isinstance(thresholds, OperationsThresholds):
        raise ProspectorContractError("thresholds must be OperationsThresholds")

    failed = []
    if (
        thresholds.max_stale_claims is not None
        and snapshot.stale_claims > thresholds.max_stale_claims
    ):
        failed.append("stale_claims")
    if (
        thresholds.max_ready_age_seconds is not None
        and snapshot.oldest_ready_age_seconds is not None
        and snapshot.oldest_ready_age_seconds > thresholds.max_ready_age_seconds
    ):
        failed.append("oldest_ready_age")
    if (
        thresholds.max_feedback_projection_lag_events is not None
        and snapshot.feedback_projection_lag_events
        > thresholds.max_feedback_projection_lag_events
    ):
        failed.append("feedback_projection_lag")
    if (
        thresholds.max_active_checkpoint_age_seconds is not None
        and snapshot.oldest_active_checkpoint_age_seconds is not None
        and snapshot.oldest_active_checkpoint_age_seconds
        > thresholds.max_active_checkpoint_age_seconds
    ):
        failed.append("active_checkpoint_age")

    return OperationsHealth(
        status="degraded" if failed else "ok",
        failed_checks=tuple(failed),
    )
