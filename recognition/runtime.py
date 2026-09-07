from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from organizations.models import Organization

from .achievements import grant_due_achievements
from .contracts import RecognitionSignalFact, RecognitionWindowStatus
from .engine import RuleSpec, evaluate_rule
from .models import (
    PolicyStatus, RecognitionAllocation, RecognitionCursor, RecognitionObjectEvaluation,
    RecognitionPolicy, RecognitionRule, RecognitionSignal,
)
from .services import AttributionShare, get_or_create_account, process_impact_slice


@dataclass(frozen=True)
class ResolvedShare:
    share: AttributionShare
    causal_mode: str
    strength: Decimal


def active_policy(*, at=None):
    at = at or timezone.now()
    return RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).filter(Q(effective_from__isnull=True) | Q(effective_from__lte=at)).filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at)).order_by("-version", "code").first()


def activate_due_policy(*, now=None, cursor=None):
    now = now or timezone.now()
    due = RecognitionPolicy.objects.filter(status=PolicyStatus.SCHEDULED, effective_from__lte=now).order_by("effective_from", "version").first()
    if due is None:
        return active_policy(at=now)
    if cursor is not None and cursor.last_completed_end < due.effective_from:
        return active_policy(at=now)
    with transaction.atomic():
        RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).exclude(pk=due.pk).update(status=PolicyStatus.SUPERSEDED, effective_until=due.effective_from)
        RecognitionPolicy.objects.filter(pk=due.pk).update(status=PolicyStatus.ACTIVE)
    return RecognitionPolicy.objects.get(pk=due.pk)


def rule_spec(rule: RecognitionRule) -> RuleSpec:
    return RuleSpec(code=rule.code, signal_kind=rule.signal_kind, channel=rule.channel, temporal_profile=rule.temporal_profile, conditions=rule.conditions or {}, measure=rule.measure or {}, normalization=rule.normalization or {}, curve=rule.curve or {}, modulators=tuple(rule.modulators or []), aggregation=rule.aggregation, attribution=rule.attribution or {})


def signal_fact(signal: RecognitionSignal) -> RecognitionSignalFact:
    return RecognitionSignalFact(signal_id=signal.signal_id, signal_kind=signal.signal_kind, object_type=signal.object_type, object_id=signal.object_id, occurred_at=signal.occurred_at, available_at=signal.available_at, outcome_identity=signal.outcome_identity, values=dict(signal.values or {}), contributors=tuple(signal.contributors or []), confidence=signal.confidence)


def _resolve_shares(contributors):
    valid = []; User = get_user_model()
    for contributor in contributors:
        if not isinstance(contributor, dict): continue
        subject_type = contributor.get("subject_type"); subject_id = contributor.get("subject_id")
        if not subject_id or subject_type not in {"profile", "space"}: continue
        try: strength = Decimal(str(contributor.get("weight", contributor.get("share", 1))))
        except Exception: continue
        if strength <= 0: continue
        subject = User.objects.filter(pk=subject_id).first() if subject_type == "profile" else Organization.objects.filter(pk=subject_id).first()
        if subject is None: continue
        valid.append((subject_type, subject, strength, str(contributor.get("causal_mode", "operate"))))
    total = sum((row[2] for row in valid), Decimal("0"))
    if total <= 0: return tuple()
    return tuple(ResolvedShare(share=AttributionShare(share=strength / total, profile=subject if subject_type == "profile" else None, space=subject if subject_type == "space" else None, description="Valeur rendue possible dans Makolo"), causal_mode=mode, strength=strength) for subject_type, subject, strength, mode in valid)


def _points_target(policy):
    factor = max(Decimal("0"), Decimal(str((policy.parameters or {}).get("credits_per_utility", "1"))))
    def target(cumulative): return int((Decimal(cumulative) * factor).to_integral_value(rounding=ROUND_FLOOR))
    return target


def signal_provider(starts_at, ends_at):
    return RecognitionSignal.objects.filter(processed_at__isnull=True, available_at__gte=starts_at, available_at__lt=ends_at).order_by("available_at", "created_at", "id")


def process_signal(*, signal, window, policy):
    rules = list(policy.rules.filter(enabled=True, signal_kind=signal.signal_kind).order_by("priority", "code")); fact = signal_fact(signal); processed = 0
    for rule in rules:
        evaluated = evaluate_rule(signal=fact, rule=rule_spec(rule), parameters=policy.parameters or {}, policy_version=policy.version_key)
        if evaluated is None: continue
        resolved = _resolve_shares(evaluated.attribution_shares)
        result = process_impact_slice(window=window, slice_key=evaluated.slice_key, accrual_key=evaluated.accrual_key, channel=evaluated.channel.value, temporal_profile=evaluated.temporal_profile.value, occurred_at=fact.occurred_at, available_at=fact.available_at, impact_delta=evaluated.utility_delta, attribution_shares=[item.share for item in resolved], points_target_for_cumulative=_points_target(policy), policy_version=policy.version_key, metadata={"signal_id": signal.signal_id, "rule": rule.code, "object_type": signal.object_type, "object_id": signal.object_id})
        evaluation, _ = RecognitionObjectEvaluation.objects.get_or_create(receipt=result.receipt, defaults={"window": window, "rule": rule, "object_type": signal.object_type, "object_id": signal.object_id, "utility_delta": evaluated.utility_delta, "pool_points": result.receipt.pool_points, "unattributed_points": result.receipt.unattributed_points, "explanation": evaluated.explanation})
        by_subject = {item.share.subject_key(): item for item in resolved}
        for grant in result.grants:
            key = f"profile:{grant.account.profile_id}" if grant.account.profile_id else f"space:{grant.account.space_id}"; detail = by_subject.get(key)
            RecognitionAllocation.objects.get_or_create(evaluation=evaluation, account=grant.account, causal_mode=(detail.causal_mode if detail else "operate"), defaults={"causal_strength": detail.strength if detail else Decimal("1"), "share": detail.share.share if detail else (Decimal(grant.points) / Decimal(max(result.receipt.pool_points, 1))), "points": grant.points, "evidence": {"signal_id": signal.signal_id, "outcome_identity": signal.outcome_identity}})
            grant.account.refresh_from_db(); grant_due_achievements(account=grant.account, evaluation=evaluation)
        processed += int(result.created)
    RecognitionSignal.objects.filter(pk=signal.pk, processed_at__isnull=True).update(processed_at=timezone.now())
    return processed


def run_default_recognition_cycle(*, now=None, max_windows=7):
    from .services import complete_window, ensure_cursor, get_due_window, mark_window_running
    now = now or timezone.now(); cursor = RecognitionCursor.objects.filter(pk="recognition-v1").first()
    policy = activate_due_policy(now=now, cursor=cursor)
    if policy is None: return {"status": "no_active_policy", "processed_slices": 0, "issued_points": 0}
    window_hours = policy.standard_window_hours
    if cursor and cursor.policy_version != policy.version_key:
        open_windows = cursor.evaluation_windows.exclude(status=RecognitionWindowStatus.COMPLETED.value).exists()
        if open_windows: return {"status": "policy_transition_waiting", "processed_slices": 0, "issued_points": 0}
        cursor.policy_version = policy.version_key; cursor.window_size_hours = window_hours; cursor.save(update_fields=["policy_version", "window_size_hours", "updated_at"])
    cursor = ensure_cursor(key="recognition-v1", policy_version=policy.version_key, window_size_hours=window_hours, start_at=now - timedelta(hours=window_hours))
    total_slices = total_points = windows = 0
    for _ in range(max(int(max_windows), 1)):
        window = get_due_window(cursor=cursor, now=now)
        if window is None: break
        mark_window_running(window)
        for signal in signal_provider(window.starts_at, window.ends_at): total_slices += process_signal(signal=signal, window=window, policy=policy)
        window = complete_window(window=window, cursor=cursor); total_points += window.issued_points; windows += 1; cursor.refresh_from_db()
    return {"status": "ok", "windows": windows, "processed_slices": total_slices, "issued_points": total_points}
