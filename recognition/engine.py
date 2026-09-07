from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from .contracts import ImpactChannel, PolicyRuleResult, RecognitionSignalFact, TemporalProfile
from .policy_dsl import decimal_value, finalize_utility, measure_value


@dataclass(frozen=True, slots=True)
class RuleSpec:
    code: str
    signal_kind: str
    channel: str
    temporal_profile: str
    scope: dict[str, Any]
    conditions: dict[str, Any]
    measure: dict[str, Any]
    normalization: dict[str, Any]
    curve: dict[str, Any]
    modulators: tuple[str, ...]
    aggregation: str
    attribution: dict[str, Any]
    combination: str = "additive"


def _ordered(signals: Iterable[RecognitionSignalFact]):
    return tuple(sorted(signals, key=lambda item: (item.available_at, item.occurred_at, item.signal_id)))


def _aggregate(rows, aggregation):
    if not rows:
        return Decimal("0")
    if aggregation == "COUNT":
        return Decimal(len(rows))
    if aggregation == "COUNT_DISTINCT":
        return Decimal(len({signal.outcome_identity for signal, _ in rows}))
    if aggregation == "SUM_DISTINCT_OUTCOME":
        by_outcome = {}
        for signal, measured in rows:
            by_outcome.setdefault(signal.outcome_identity, measured)
        return sum(by_outcome.values(), Decimal("0"))
    values = [measured for _, measured in rows]
    if aggregation == "SUM":
        return sum(values, Decimal("0"))
    if aggregation == "AVG":
        return sum(values, Decimal("0")) / Decimal(len(values))
    if aggregation == "MIN":
        return min(values)
    if aggregation == "MAX":
        return max(values)
    if aggregation == "DELTA":
        return values[-1] - values[0] if len(values) > 1 else values[0]
    if aggregation == "LATEST_STATE":
        return values[-1]
    raise ValueError(f"Unsupported Recognition aggregation: {aggregation}")


def _combined_contributors(rows, attribution):
    strategy = (attribution or {}).get("strategy", "signal_contributors")
    if strategy == "unattributed":
        return tuple()
    merged = {}
    for signal, _ in rows:
        for contributor in signal.contributors:
            if not isinstance(contributor, dict):
                continue
            subject_type = contributor.get("subject_type")
            if strategy == "profile_only" and subject_type != "profile":
                continue
            if strategy == "space_only" and subject_type != "space":
                continue
            subject_id = contributor.get("subject_id")
            if subject_type not in {"profile", "space"} or not subject_id:
                continue
            causal_mode = str(contributor.get("causal_mode", "operate"))
            try:
                weight = decimal_value(contributor.get("weight", contributor.get("share", 1)))
            except Exception:
                continue
            if weight <= 0:
                continue
            key = (subject_type, str(subject_id), causal_mode)
            merged[key] = merged.get(key, Decimal("0")) + weight
    return tuple(
        {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "causal_mode": causal_mode,
            "weight": str(weight),
        }
        for (subject_type, subject_id, causal_mode), weight in sorted(merged.items())
    )


def evaluate_rule_group(
    *,
    signals: Iterable[RecognitionSignalFact],
    rule: RuleSpec,
    parameters: dict[str, Any],
    policy_version: str,
    group_identity: str,
) -> PolicyRuleResult | None:
    """Pure deterministic evaluation for one Rule over one object/window group."""
    candidates = [item for item in _ordered(signals) if item.signal_kind == rule.signal_kind]
    rows = []
    for signal in candidates:
        measured = measure_value(rule, values=signal.values, parameters=parameters)
        if measured is not None:
            rows.append((signal, measured))
    if not rows:
        return None

    aggregate_value = _aggregate(rows, rule.aggregation)
    confidence = sum((signal.confidence for signal, _ in rows), Decimal("0")) / Decimal(len(rows))
    modulator_values = dict(rows[-1][0].values)
    utility = finalize_utility(
        rule,
        aggregate_value=aggregate_value,
        confidence=confidence,
        modulator_values=modulator_values,
    )
    if utility <= 0:
        return None

    contributors = _combined_contributors(rows, rule.attribution)
    if (rule.attribution or {}).get("require_contributor") and not contributors:
        return None

    first_signal = rows[0][0]
    identity = f"{policy_version}|{rule.code}|{group_identity}|{rule.channel}"
    slice_key = "recognition:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    accrual_key = f"{first_signal.object_type}:{first_signal.object_id}:{rule.code}:{rule.channel}"
    return PolicyRuleResult(
        rule_code=rule.code,
        channel=ImpactChannel(rule.channel),
        temporal_profile=TemporalProfile(rule.temporal_profile),
        utility_delta=Decimal(utility),
        accrual_key=accrual_key,
        slice_key=slice_key,
        attribution_shares=contributors,
        explanation={
            "signal_kind": rule.signal_kind,
            "aggregation": rule.aggregation,
            "combination": rule.combination,
            "signals": len(rows),
            "outcomes": len({signal.outcome_identity for signal, _ in rows}),
            "aggregate_value": str(aggregate_value),
            "utility_delta": str(utility),
        },
    )


def evaluate_rule(*, signal: RecognitionSignalFact, rule: RuleSpec, parameters: dict[str, Any], policy_version: str) -> PolicyRuleResult | None:
    """Compatibility wrapper for deterministic single-Signal evaluation."""
    return evaluate_rule_group(
        signals=(signal,),
        rule=rule,
        parameters=parameters,
        policy_version=policy_version,
        group_identity=signal.outcome_identity,
    )
