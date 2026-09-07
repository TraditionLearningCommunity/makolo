from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR

from .engine import evaluate_rule_group
from .models import RecognitionSignal
from .runtime import rule_spec, signal_fact


def _select_combined(rows):
    selected = []
    grouped = defaultdict(list)
    for rule, result in rows:
        grouped[(rule.signal_kind, rule.channel)].append((rule, result))
    for group_rows in grouped.values():
        selected.extend((rule, result) for rule, result in group_rows if rule.combination == "additive")
        exclusive = [(rule, result) for rule, result in group_rows if rule.combination == "exclusive"]
        maximum = [(rule, result) for rule, result in group_rows if rule.combination == "max"]
        if exclusive:
            selected.append(exclusive[0])
        if maximum:
            selected.append(max(maximum, key=lambda row: (row[1].utility_delta, -row[0].priority, row[0].code)))
    return selected


def simulate_policy(*, policy, starts_at, ends_at):
    """Replay historical safe Signals without receipts, ledger entries or consumption."""
    rules = list(policy.rules.filter(enabled=True).order_by("priority", "code"))
    signals = list(
        RecognitionSignal.objects.filter(available_at__gte=starts_at, available_at__lt=ends_at)
        .order_by("available_at", "id")
    )
    by_object = defaultdict(list)
    subject_kinds = defaultdict(int)
    for signal in signals:
        by_object[(signal.object_type, signal.object_id)].append(signal)
        for contributor in signal.contributors or []:
            if isinstance(contributor, dict) and contributor.get("subject_type") in {"profile", "space"}:
                subject_kinds[contributor["subject_type"]] += 1

    utility_by_accrual = defaultdict(lambda: Decimal("0"))
    matches = 0
    for (object_type, object_id), group in by_object.items():
        facts = tuple(signal_fact(signal) for signal in group)
        kinds = {signal.signal_kind for signal in group}
        evaluated = []
        group_identity = f"simulation:{object_type}:{object_id}:{starts_at.isoformat()}:{ends_at.isoformat()}"
        for rule in rules:
            if rule.signal_kind not in kinds:
                continue
            result = evaluate_rule_group(
                signals=facts,
                rule=rule_spec(rule),
                parameters=policy.parameters or {},
                policy_version=policy.version_key,
                group_identity=group_identity,
            )
            if result is not None:
                evaluated.append((rule, result))
        for _rule, result in _select_combined(evaluated):
            matches += 1
            utility_by_accrual[result.accrual_key] += result.utility_delta

    factor = Decimal(str((policy.parameters or {}).get("credits_per_utility", "1")))
    projected = sum(
        int((utility * factor).to_integral_value(rounding=ROUND_FLOOR))
        for utility in utility_by_accrual.values()
    )
    return {
        "signals": len(signals),
        "matches": matches,
        "objects": len(by_object),
        "accruals": len(utility_by_accrual),
        "projected_credits": projected,
        "profile_evidence": subject_kinds["profile"],
        "space_evidence": subject_kinds["space"],
    }
