from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrchestrationDecision(str, Enum):
    APPLY = "apply"
    NO_ACTION = "no_action"
    DEFER = "defer"
    REVIEW = "review"
    REJECT = "reject"
    CONFLICT = "conflict"


class OrchestrationTrigger(str, Enum):
    RESOLVED_MATERIAL = "resolved_material"
    USER_COMMAND = "user_command"
    DOMAIN_EVENT = "domain_event"
    UNIVERSE_RESULT = "universe_result"


@dataclass(frozen=True, slots=True)
class OrchestrationContext:
    actor: Any = None
    represented_space: Any = None
    trigger: OrchestrationTrigger = OrchestrationTrigger.RESOLVED_MATERIAL
    request_ref: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "trigger", OrchestrationTrigger(self.trigger))


@dataclass(frozen=True, slots=True)
class OwnerDecision:
    decision: OrchestrationDecision
    reason_code: str
    operation: str | None = None
    applied_ref: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "decision", OrchestrationDecision(self.decision))
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError("reason_code must not be empty")
        if self.operation is not None and not str(self.operation).strip():
            raise ValueError("operation must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class OrchestrationDecisionRecord:
    resolution_ref: str
    assertion_ref: str
    decision: OrchestrationDecision
    reason_code: str
    owner_domain: str | None = None
    operation: str | None = None
    canonical_object_ref: str | None = None
    applied_ref: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "decision", OrchestrationDecision(self.decision))


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    resolution_ref: str
    source_outcome: str
    decisions: tuple[OrchestrationDecisionRecord, ...]

    @property
    def applied_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.APPLY for item in self.decisions)

    @property
    def no_action_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.NO_ACTION for item in self.decisions)

    @property
    def review_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.REVIEW for item in self.decisions)

    @property
    def conflict_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.CONFLICT for item in self.decisions)

    @property
    def deferred_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.DEFER for item in self.decisions)

    @property
    def rejected_count(self) -> int:
        return sum(item.decision is OrchestrationDecision.REJECT for item in self.decisions)
