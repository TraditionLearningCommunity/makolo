from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from .contracts import ProspectingTarget
from .errors import ProspectorContractError

FEEDBACK_SCOPE_KINDS = frozenset(
    {
        "lineage_target",
        "method",
        "provider",
        "mission",
        "campaign",
        "branch",
    }
)


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ProspectorContractError(f"{name} must not be empty")
    return value


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ProspectorContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class FeedbackSignal(str, Enum):
    OBSERVATION_VALID = "observation_valid"
    STRUCTURED_INFORMATION = "structured_information"
    REALITY_NEW = "reality_new"
    REALITY_REFRESHED = "reality_refreshed"
    NO_USEFUL_INFORMATION = "no_useful_information"
    DOWNSTREAM_REJECTED = "downstream_rejected"


class FeedbackProducer(str, Enum):
    OBSERVER = "observer"
    INTERPRETER = "interpreter"
    RESOLVER = "resolver"
    ORCHESTRATOR = "orchestrator"


@dataclass(frozen=True, slots=True, order=True)
class LearningScope:
    kind: str
    key: str

    def __post_init__(self) -> None:
        kind = _required_text("scope kind", self.kind)
        key = _required_text("scope key", self.key)
        if kind not in FEEDBACK_SCOPE_KINDS:
            raise ProspectorContractError(f"unsupported feedback scope kind {kind!r}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "key", key)


@dataclass(frozen=True, slots=True)
class ProspectingFeedback:
    event_key: str
    target_key: str
    signal: FeedbackSignal
    producer: FeedbackProducer
    source_ref: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_key", _required_text("event_key", self.event_key))
        object.__setattr__(self, "target_key", _required_text("target_key", self.target_key))
        object.__setattr__(self, "source_ref", _required_text("source_ref", self.source_ref))
        try:
            signal = FeedbackSignal(self.signal)
        except ValueError as exc:
            raise ProspectorContractError("invalid feedback signal") from exc
        try:
            producer = FeedbackProducer(self.producer)
        except ValueError as exc:
            raise ProspectorContractError("invalid feedback producer") from exc
        object.__setattr__(self, "signal", signal)
        object.__setattr__(self, "producer", producer)
        object.__setattr__(
            self,
            "occurred_at",
            _utc_datetime("occurred_at", self.occurred_at),
        )


@dataclass(frozen=True, slots=True)
class FeedbackPolicy:
    policy_key: str
    weights: Mapping[FeedbackSignal, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_key", _required_text("policy_key", self.policy_key))
        if not isinstance(self.weights, Mapping):
            raise ProspectorContractError("feedback weights must be a mapping")
        normalized = {}
        for raw_signal, raw_weight in self.weights.items():
            try:
                signal = FeedbackSignal(raw_signal)
            except ValueError as exc:
                raise ProspectorContractError("unsupported feedback signal weight") from exc
            if not isinstance(raw_weight, int) or isinstance(raw_weight, bool):
                raise ProspectorContractError("feedback weights must be integers")
            normalized[signal] = raw_weight
        missing = set(FeedbackSignal) - set(normalized)
        if missing:
            raise ProspectorContractError(
                "feedback policy must explicitly weight every signal"
            )
        object.__setattr__(self, "weights", MappingProxyType(normalized))

    @property
    def fingerprint(self) -> str:
        payload = {
            "policy_key": self.policy_key,
            "weights": {
                signal.value: self.weights[signal]
                for signal in sorted(FeedbackSignal, key=lambda item: item.value)
            },
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AdaptivePolicy:
    feedback: FeedbackPolicy
    dimension_weights: Mapping[str, int]
    min_samples_for_exploitation: int
    exploration_numerator: int
    exploration_denominator: int
    candidate_pool_multiplier: int
    projection_batch_size: int

    def __post_init__(self) -> None:
        if not isinstance(self.dimension_weights, Mapping):
            raise ProspectorContractError("dimension_weights must be a mapping")
        weights = {}
        for kind, weight in self.dimension_weights.items():
            if kind not in FEEDBACK_SCOPE_KINDS:
                raise ProspectorContractError(
                    f"unsupported adaptive dimension {kind!r}"
                )
            if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
                raise ProspectorContractError(
                    "adaptive dimension weights must be positive integers"
                )
            weights[kind] = weight
        if not weights:
            raise ProspectorContractError("dimension_weights must not be empty")
        object.__setattr__(self, "dimension_weights", MappingProxyType(weights))
        for name in (
            "min_samples_for_exploitation",
            "exploration_denominator",
            "candidate_pool_multiplier",
            "projection_batch_size",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ProspectorContractError(f"{name} must be a positive integer")
        if (
            not isinstance(self.exploration_numerator, int)
            or isinstance(self.exploration_numerator, bool)
            or self.exploration_numerator < 0
            or self.exploration_numerator > self.exploration_denominator
        ):
            raise ProspectorContractError(
                "exploration_numerator must be between 0 and exploration_denominator"
            )

    def exploration_slots(self, limit: int) -> int:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ProspectorContractError("limit must be a positive integer")
        if self.exploration_numerator == 0:
            return 0
        return min(
            limit,
            (
                limit * self.exploration_numerator
                + self.exploration_denominator
                - 1
            )
            // self.exploration_denominator,
        )


@dataclass(frozen=True, slots=True)
class LearningStat:
    scope: LearningScope
    sample_count: int
    score_sum: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or self.sample_count < 0
        ):
            raise ProspectorContractError("sample_count must be non-negative")
        if not isinstance(self.score_sum, int) or isinstance(self.score_sum, bool):
            raise ProspectorContractError("score_sum must be an integer")


@dataclass(frozen=True, slots=True)
class CandidateLearning:
    support_samples: int
    weighted_samples: int
    weighted_score_sum: int

    @property
    def mean_score(self) -> Fraction:
        if self.weighted_samples == 0:
            return Fraction(0, 1)
        return Fraction(self.weighted_score_sum, self.weighted_samples)


def feedback_scopes_for_target(target: ProspectingTarget) -> Tuple[LearningScope, ...]:
    if not isinstance(target, ProspectingTarget):
        raise ProspectorContractError("target must be a ProspectingTarget")

    scopes = {LearningScope("lineage_target", target.target_key)}
    for evidence in target.evidence:
        scopes.add(LearningScope("method", evidence.method))
        if evidence.provider:
            scopes.add(LearningScope("provider", evidence.provider))
        if evidence.source_target_key:
            scopes.add(LearningScope("lineage_target", evidence.source_target_key))

    context_fields = {
        "mission": "mission_key",
        "campaign": "campaign_key",
        "branch": "branch_key",
    }
    for kind, field_name in context_fields.items():
        value = target.policy_context.get(field_name)
        if isinstance(value, str) and value.strip():
            scopes.add(LearningScope(kind, value.strip()))

    return tuple(sorted(scopes))


def score_target(
    target: ProspectingTarget,
    *,
    stats: Mapping[LearningScope, LearningStat],
    policy: AdaptivePolicy,
) -> CandidateLearning:
    weighted_samples = 0
    weighted_score_sum = 0
    support_samples = 0

    for scope in feedback_scopes_for_target(target):
        dimension_weight = policy.dimension_weights.get(scope.kind)
        if dimension_weight is None:
            continue
        stat = stats.get(scope)
        if stat is None:
            continue
        support_samples = max(support_samples, stat.sample_count)
        weighted_samples += stat.sample_count * dimension_weight
        weighted_score_sum += stat.score_sum * dimension_weight

    return CandidateLearning(
        support_samples=support_samples,
        weighted_samples=weighted_samples,
        weighted_score_sum=weighted_score_sum,
    )
