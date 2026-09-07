from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from .engine import evaluate_rule_group
from .models import RecognitionSignal
from .runtime import _points_target, _select_combined, _temporal_delta, rule_spec, signal_fact


def simulate_policy(*, policy, starts_at, ends_at):
    """Replay historical safe Signals with the same object/temporal pool semantics, without writes."""
    rules = list(policy.rules.filter(enabled=True).order_by("priority", "code"))
    signals = list(
        RecognitionSignal.objects.filter(available_at__gte=starts_at, available_at__lt=ends_at)
        .order_by("available_at", "id")
    )
    subject_kinds = defaultdict(int)
    for signal in signals:
        for contributor in signal.contributors or []:
            if isinstance(contributor, dict) and contributor.get("subject_type") in {"profile", "space"}:
                subject_kinds[contributor["subject_type"]] += 1

    window_size = timedelta(hours=policy.standard_window_hours)
    semantic_window_hours = int((policy.parameters or {}).get("semantic_window_hours", policy.standard_window_hours) or policy.standard_window_hours)
    semantic_window_hours = max(1, min(semantic_window_hours, 8760))
    states = defaultdict(dict)
    cumulative_utility = defaultdict(lambda: Decimal("0"))
    cumulative_points = defaultdict(int)
    target_for = _points_target(policy)
    matches = projected = 0
    objects_seen = set()

    cursor = starts_at
    while cursor < ends_at:
        bucket_end = min(cursor + window_size, ends_at)
        bucket_signals = [signal for signal in signals if cursor <= signal.available_at < bucket_end]
        by_object = defaultdict(list)
        for signal in bucket_signals:
            by_object[(signal.object_type, signal.object_id)].append(signal)
        for object_key, group in by_object.items():
            objects_seen.add(object_key)
            facts = tuple(signal_fact(signal) for signal in group)
            kinds = {signal.signal_kind for signal in group}
            evaluated = []
            group_identity = f"simulation:{object_key[0]}:{object_key[1]}:{cursor.isoformat()}:{bucket_end.isoformat()}"
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
            selected = _select_combined(evaluated)
            matches += len(selected)
            utility_delta = Decimal("0")
            for rule, result in selected:
                occurred_at = max(fact.occurred_at for fact in facts if fact.signal_kind == rule.signal_kind)
                delta, state_after = _temporal_delta(
                    rule=rule,
                    evaluated=result,
                    prior_state=states[object_key].get(rule.code),
                    occurred_at=occurred_at,
                    semantic_window_hours=semantic_window_hours,
                )
                states[object_key][rule.code] = state_after
                utility_delta += delta
            previous_target = cumulative_points[object_key]
            cumulative_utility[object_key] += utility_delta
            new_target = target_for(cumulative_utility[object_key])
            projected += max(0, new_target - previous_target)
            cumulative_points[object_key] = max(previous_target, new_target)
        cursor = bucket_end

    return {
        "signals": len(signals),
        "matches": matches,
        "objects": len(objects_seen),
        "accruals": len(cumulative_utility),
        "projected_credits": projected,
        "profile_evidence": subject_kinds["profile"],
        "space_evidence": subject_kinds["space"],
    }
