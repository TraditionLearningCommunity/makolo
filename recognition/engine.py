from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from .contracts import ImpactChannel, PolicyRuleResult, RecognitionSignalFact, TemporalProfile
from .policy_dsl import apply_curve, decimal_value, measure_value


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
    return tuple(sorted(signals, key=lambda item: (item.occurred_at, item.available_at, item.signal_id)))


def _modulated_measure(rule, signal, measured):
    result = Decimal(measured)
    for name in rule.modulators or ():
        if name == "confidence":
            factor = max(Decimal("0"), min(Decimal("1"), Decimal(signal.confidence)))
        else:
            factor = max(Decimal("0"), decimal_value(signal.values.get(name, 1)))
        result *= factor
    return result


def _aggregate_metrics(rows, aggregation):
    if not rows:
        return {"value": Decimal("0"), "sum": Decimal("0"), "count": 0, "first": Decimal("0"), "last": Decimal("0"), "min": Decimal("0"), "max": Decimal("0"), "outcomes": 0}
    distinct = {}
    for signal, measured in rows:
        distinct.setdefault(signal.outcome_identity, measured)
    values = [measured for _, measured in rows]
    total = sum(values, Decimal("0"))
    if aggregation == "COUNT":
        value = Decimal(len(rows))
    elif aggregation == "COUNT_DISTINCT":
        value = Decimal(len(distinct))
    elif aggregation == "SUM_DISTINCT_OUTCOME":
        value = sum(distinct.values(), Decimal("0"))
    elif aggregation == "SUM":
        value = total
    elif aggregation == "AVG":
        value = total / Decimal(len(values))
    elif aggregation == "MIN":
        value = min(values)
    elif aggregation == "MAX":
        value = max(values)
    elif aggregation == "DELTA":
        value = values[-1] - values[0] if len(values) > 1 else values[0]
    elif aggregation == "LATEST_STATE":
        value = values[-1]
    else:
        raise ValueError(f"Unsupported Recognition aggregation: {aggregation}")
    return {
        "value": value,
        "sum": total,
        "count": len(values),
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
        "outcomes": len(distinct),
    }


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
        {"subject_type": subject_type, "subject_id": subject_id, "causal_mode": causal_mode, "weight": str(weight)}
        for (subject_type, subject_id, causal_mode), weight in sorted(merged.items())
    )


def evaluate_rule_group(*, signals: Iterable[RecognitionSignalFact], rule: RuleSpec, parameters: dict[str, Any], policy_version: str, group_identity: str) -> PolicyRuleResult | None:
    """Pure evaluation of one Rule over one delivered group; runtime owns cumulative temporal state."""
    candidates = [item for item in _ordered(signals) if item.signal_kind == rule.signal_kind]
    rows = []
    for signal in candidates:
        measured = measure_value(rule, values=signal.values, parameters=parameters)
        if measured is not None:
            rows.append((signal, _modulated_measure(rule, signal, measured)))
    if not rows:
        return None

    metrics = _aggregate_metrics(rows, rule.aggregation)
    normalized = apply_curve(metrics["value"], rule.normalization or {"kind": "LINEAR", "factor": 1})
    utility = apply_curve(normalized, rule.curve or {"kind": "LINEAR", "factor": 1})
    contributors = _combined_contributors(rows, rule.attribution)
    if (rule.attribution or {}).get("require_contributor") and not contributors:
        return None

    first_signal = rows[0][0]
    identity = f"{policy_version}|{rule.code}|{group_identity}|{rule.channel}"
    return PolicyRuleResult(
        rule_code=rule.code,
        channel=ImpactChannel(rule.channel),
        temporal_profile=TemporalProfile(rule.temporal_profile),
        utility_delta=max(Decimal("0"), Decimal(utility)),
        accrual_key=f"{first_signal.object_type}:{first_signal.object_id}:{rule.code}:{rule.channel}",
        slice_key="recognition:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        attribution_shares=contributors,
        explanation={
            "signal_kind": rule.signal_kind,
            "aggregation": rule.aggregation,
            "combination": rule.combination,
            "signals": metrics["count"],
            "outcomes": metrics["outcomes"],
            "aggregate_value": str(metrics["value"]),
            "aggregate_sum": str(metrics["sum"]),
            "first_value": str(metrics["first"]),
            "last_value": str(metrics["last"]),
            "min_value": str(metrics["min"]),
            "max_value": str(metrics["max"]),
            "utility_delta": str(max(Decimal("0"), Decimal(utility))),
        },
    )


def evaluate_rule(*, signal: RecognitionSignalFact, rule: RuleSpec, parameters: dict[str, Any], policy_version: str) -> PolicyRuleResult | None:
    return evaluate_rule_group(signals=(signal,), rule=rule, parameters=parameters, policy_version=policy_version, group_identity=signal.outcome_identity)
