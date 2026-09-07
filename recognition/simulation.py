from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR

from .engine import evaluate_rule
from .runtime import rule_spec, signal_fact
from .models import RecognitionSignal


def simulate_policy(*, policy, starts_at, ends_at):
    """Evaluate historical Signals without receipts, ledger entries or consumption."""
    rules = list(policy.rules.filter(enabled=True).order_by("priority", "code"))
    by_kind = defaultdict(list)
    for rule in rules:
        by_kind[rule.signal_kind].append(rule)
    utility_by_accrual = defaultdict(lambda: Decimal("0"))
    signal_count = 0
    matched_count = 0
    subject_kinds = defaultdict(int)
    for signal in RecognitionSignal.objects.filter(available_at__gte=starts_at, available_at__lt=ends_at).order_by("available_at", "id"):
        signal_count += 1
        fact = signal_fact(signal)
        for contributor in signal.contributors or []:
            if isinstance(contributor, dict) and contributor.get("subject_type") in {"profile", "space"}:
                subject_kinds[contributor["subject_type"]] += 1
        for rule in by_kind.get(signal.signal_kind, []):
            result = evaluate_rule(signal=fact, rule=rule_spec(rule), parameters=policy.parameters or {}, policy_version=policy.version_key)
            if result is None:
                continue
            matched_count += 1
            utility_by_accrual[result.accrual_key] += result.utility_delta
    factor = Decimal(str((policy.parameters or {}).get("credits_per_utility", "1")))
    projected = sum(int((utility * factor).to_integral_value(rounding=ROUND_FLOOR)) for utility in utility_by_accrual.values())
    return {
        "signals": signal_count,
        "matches": matched_count,
        "accruals": len(utility_by_accrual),
        "projected_credits": projected,
        "profile_evidence": subject_kinds["profile"],
        "space_evidence": subject_kinds["space"],
    }
