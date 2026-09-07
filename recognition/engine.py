from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .contracts import ImpactChannel, PolicyRuleResult, RecognitionSignalFact, TemporalProfile
from .policy_dsl import normalized_utility


@dataclass(frozen=True, slots=True)
class RuleSpec:
    code: str
    signal_kind: str
    channel: str
    temporal_profile: str
    conditions: dict[str, Any]
    measure: dict[str, Any]
    normalization: dict[str, Any]
    curve: dict[str, Any]
    modulators: tuple[str, ...]
    aggregation: str
    attribution: dict[str, Any]


def evaluate_rule(*, signal: RecognitionSignalFact, rule: RuleSpec, parameters: dict[str, Any], policy_version: str) -> PolicyRuleResult | None:
    """Pure deterministic Recognition rule evaluation. No ORM, I/O or clock."""
    if signal.signal_kind != rule.signal_kind:
        return None
    utility = normalized_utility(rule, values=signal.values, parameters=parameters, confidence=signal.confidence)
    if utility <= 0:
        return None
    identity = f"{policy_version}|{rule.code}|{signal.outcome_identity}|{rule.channel}"
    slice_key = "recognition:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    accrual_key = f"{signal.object_type}:{signal.object_id}:{rule.code}:{rule.channel}"
    return PolicyRuleResult(
        rule_code=rule.code,
        channel=ImpactChannel(rule.channel),
        temporal_profile=TemporalProfile(rule.temporal_profile),
        utility_delta=Decimal(utility),
        accrual_key=accrual_key,
        slice_key=slice_key,
        attribution_shares=signal.contributors,
        explanation={
            "signal_kind": signal.signal_kind,
            "outcome_identity": signal.outcome_identity,
            "aggregation": rule.aggregation,
            "utility_delta": str(utility),
        },
    )
