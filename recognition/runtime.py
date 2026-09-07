from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from organizations.models import Organization

from .achievements import grant_due_achievements
from .contracts import ImpactChannel, RecognitionLedgerKind, RecognitionSignalFact, RecognitionWindowStatus, TemporalProfile
from .engine import RuleSpec, evaluate_rule_group
from .models import (
    CausalMode, PolicyStatus, RecognitionAllocation, RecognitionCursor,
    RecognitionObjectEvaluation, RecognitionPolicy, RecognitionRule, RecognitionSignal,
)
from .policy_dsl import apply_curve, decimal_value
from .services import AttributionShare, process_impact_slice, release_due_pending_grants


PUBLISHED_POLICY_STATUSES = (
    PolicyStatus.ACTIVE,
    PolicyStatus.SUPERSEDED,
    PolicyStatus.RETIRED,
)


@dataclass(frozen=True)
class ResolvedShare:
    share: AttributionShare
    causal_mode: str
    strength: Decimal


def active_policy(*, at=None):
    at = at or timezone.now()
    return (
        RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE)
        .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=at))
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at))
        .order_by(F("effective_from").desc(nulls_last=True), "-version", "code")
        .first()
    )


def policy_for_fact(*, at):
    """Published earning Policy applicable to the immutable domain fact time.

    Evaluation windows are observation/watermark cadence. A fact discovered late
    must not be repriced by a Policy that became effective after it occurred.
    """
    if at is None:
        raise ValidationError("occurred_at est obligatoire pour résoudre la Policy Recognition.")
    return (
        RecognitionPolicy.objects.filter(status__in=PUBLISHED_POLICY_STATUSES)
        .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=at))
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at))
        .order_by(F("effective_from").desc(nulls_last=True), "-version", "code")
        .first()
    )


def activate_due_policy(*, now=None, cursor=None):
    now = now or timezone.now()
    due = (
        RecognitionPolicy.objects.filter(status=PolicyStatus.SCHEDULED, effective_from__lte=now)
        .order_by("effective_from", "version", "code")
        .first()
    )
    if due is None:
        return active_policy(at=now)
    if cursor is not None and cursor.last_completed_end < due.effective_from:
        return active_policy(at=now)
    with transaction.atomic():
        RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).exclude(pk=due.pk).update(
            status=PolicyStatus.SUPERSEDED, effective_until=due.effective_from,
        )
        RecognitionPolicy.objects.filter(pk=due.pk).update(status=PolicyStatus.ACTIVE)
    return RecognitionPolicy.objects.get(pk=due.pk)


def rule_spec(rule: RecognitionRule) -> RuleSpec:
    return RuleSpec(
        code=rule.code, signal_kind=rule.signal_kind, channel=rule.channel,
        temporal_profile=rule.temporal_profile, scope=rule.scope or {}, conditions=rule.conditions or {},
        measure=rule.measure or {}, normalization=rule.normalization or {}, curve=rule.curve or {},
        modulators=tuple(rule.modulators or []), aggregation=rule.aggregation,
        attribution=rule.attribution or {}, combination=rule.combination,
    )


def signal_fact(signal: RecognitionSignal) -> RecognitionSignalFact:
    return RecognitionSignalFact(
        signal_id=signal.signal_id, signal_kind=signal.signal_kind,
        object_type=signal.object_type, object_id=signal.object_id,
        occurred_at=signal.occurred_at, available_at=signal.available_at,
        outcome_identity=signal.outcome_identity, values=dict(signal.values or {}),
        contributors=tuple(signal.contributors or []), confidence=signal.confidence,
    )


def _points_target(policy):
    parameters = policy.parameters or {}
    factor = max(Decimal("0"), decimal_value(parameters.get("credits_per_utility", "1")))
    credit_curve = parameters.get("credit_curve") or {"kind": "LINEAR", "factor": 1}

    def target(cumulative):
        return int((apply_curve(Decimal(cumulative), credit_curve) * factor).to_integral_value(rounding=ROUND_FLOOR))
    return target


def signal_provider(starts_at, ends_at):
    return RecognitionSignal.objects.filter(
        processed_at__isnull=True, available_at__gte=starts_at, available_at__lt=ends_at,
    ).order_by("available_at", "created_at", "id")


def _select_combined(rows):
    """rows = (rule, result, marginal_utility, state_after); MAX compares real marginal utility."""
    selected = []
    grouped = defaultdict(list)
    for row in rows:
        rule = row[0]
        grouped[(rule.signal_kind, rule.channel)].append(row)
    for group_rows in grouped.values():
        selected.extend(row for row in group_rows if row[0].combination == "additive")
        exclusive = [row for row in group_rows if row[0].combination == "exclusive"]
        maximum = [row for row in group_rows if row[0].combination == "max"]
        if exclusive:
            selected.append(exclusive[0])
        if maximum:
            selected.append(max(maximum, key=lambda row: (row[2], -row[0].priority, row[0].code)))
    return selected


def _previous_rule_states(*, object_type, object_id, policy_version):
    previous = (
        RecognitionObjectEvaluation.objects.filter(
            object_type=object_type,
            object_id=object_id,
            receipt__policy_version=policy_version,
        )
        .order_by("-created_at")
        .values_list("explanation", flat=True)
        .first()
    )
    if not isinstance(previous, dict):
        return {}
    states = previous.get("rule_states") or {}
    return dict(states) if isinstance(states, dict) else {}


def _metrics(explanation):
    return {
        "value": decimal_value(explanation.get("aggregate_value", 0)),
        "sum": decimal_value(explanation.get("aggregate_sum", explanation.get("aggregate_value", 0))),
        "count": int(explanation.get("signals", 0) or 0),
        "outcomes": int(explanation.get("outcomes", 0) or 0),
        "first": decimal_value(explanation.get("first_value", explanation.get("aggregate_value", 0))),
        "last": decimal_value(explanation.get("last_value", explanation.get("aggregate_value", 0))),
        "min": decimal_value(explanation.get("min_value", explanation.get("aggregate_value", 0))),
        "max": decimal_value(explanation.get("max_value", explanation.get("aggregate_value", 0))),
    }


def _merge_aggregate(aggregation, previous, current):
    state = dict(previous or {})
    if aggregation == "SUM":
        raw = decimal_value(state.get("sum", 0)) + current["sum"]
        state["sum"] = str(raw)
    elif aggregation == "COUNT":
        raw = Decimal(int(state.get("count", 0) or 0) + current["count"])
        state["count"] = int(raw)
    elif aggregation == "COUNT_DISTINCT":
        # RecognitionSignal enforces unique (signal_kind, outcome_identity), so distinct sets do not overlap across deliveries.
        raw = Decimal(int(state.get("outcomes", 0) or 0) + current["outcomes"])
        state["outcomes"] = int(raw)
    elif aggregation == "SUM_DISTINCT_OUTCOME":
        raw = decimal_value(state.get("sum", 0)) + current["value"]
        state["sum"] = str(raw)
    elif aggregation == "AVG":
        total = decimal_value(state.get("sum", 0)) + current["sum"]
        count = int(state.get("count", 0) or 0) + current["count"]
        raw = total / Decimal(count) if count else Decimal("0")
        state.update({"sum": str(total), "count": count})
    elif aggregation == "MIN":
        raw = current["min"] if "min" not in state else min(decimal_value(state["min"]), current["min"])
        state["min"] = str(raw)
    elif aggregation == "MAX":
        raw = current["max"] if "max" not in state else max(decimal_value(state["max"]), current["max"])
        state["max"] = str(raw)
    elif aggregation == "DELTA":
        first = decimal_value(state.get("first", current["first"]))
        last = current["last"]
        raw = last - first
        state.update({"first": str(first), "last": str(last)})
    elif aggregation == "LATEST_STATE":
        raw = current["last"]
        state["last"] = str(raw)
    else:
        raise ValueError(f"Unsupported Recognition aggregation: {aggregation}")
    state["raw"] = str(raw)
    state["aggregation"] = aggregation
    return raw, state


def _utility_for_raw(rule, raw):
    normalized = apply_curve(max(Decimal("0"), raw), rule.normalization or {"kind": "LINEAR", "factor": 1})
    return apply_curve(normalized, rule.curve or {"kind": "LINEAR", "factor": 1})


def _temporal_delta(*, rule, evaluated, prior_state):
    profile = rule.temporal_profile
    previous = dict(prior_state or {})
    if profile == TemporalProfile.WINDOW.value:
        buckets = dict(previous.get("buckets") or {})
        delta = Decimal("0")
        for item in evaluated.explanation.get("window_buckets") or []:
            key = str(item["bucket"])
            current = {
                "value": decimal_value(item["metrics"].get("value", 0)),
                "sum": decimal_value(item["metrics"].get("sum", 0)),
                "count": int(item["metrics"].get("count", 0) or 0),
                "outcomes": int(item["metrics"].get("outcomes", 0) or 0),
                "first": decimal_value(item["metrics"].get("first", 0)),
                "last": decimal_value(item["metrics"].get("last", 0)),
                "min": decimal_value(item["metrics"].get("min", 0)),
                "max": decimal_value(item["metrics"].get("max", 0)),
            }
            old_bucket = dict(buckets.get(key) or {})
            raw, new_bucket = _merge_aggregate(rule.aggregation, old_bucket, current)
            old_utility = decimal_value(old_bucket.get("utility", 0))
            new_utility = _utility_for_raw(rule, raw)
            delta += max(Decimal("0"), new_utility - old_utility)
            new_bucket["utility"] = str(new_utility)
            buckets[key] = new_bucket
        return delta, {"profile": profile, "buckets": buckets}

    raw, merged = _merge_aggregate(rule.aggregation, previous.get("aggregate") or {}, _metrics(evaluated.explanation))
    old_utility = decimal_value(previous.get("utility", 0))
    new_utility = _utility_for_raw(rule, raw)
    delta = max(Decimal("0"), new_utility - old_utility)
    return delta, {"profile": profile, "aggregate": merged, "utility": str(new_utility)}


def _resolve_subject(subject_type, subject_id):
    if subject_type == "profile":
        return get_user_model().objects.filter(pk=subject_id).first()
    if subject_type == "space":
        return Organization.objects.filter(pk=subject_id).first()
    return None


def _has_resolvable_contributor(rule, evaluated):
    if not (rule.attribution or {}).get("require_contributor"):
        return True
    strategy = (rule.attribution or {}).get("strategy", "signal_contributors")
    for contributor in evaluated.attribution_shares:
        if not isinstance(contributor, dict):
            continue
        subject_type = contributor.get("subject_type")
        if strategy == "profile_only" and subject_type != "profile":
            continue
        if strategy == "space_only" and subject_type != "space":
            continue
        if _resolve_subject(subject_type, contributor.get("subject_id")) is not None:
            return True
    return False


def _resolve_object_shares(rows, total_utility):
    if total_utility <= 0:
        return tuple()
    subject_utility = defaultdict(lambda: Decimal("0"))
    subject_modes = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    subjects = {}
    allowed_modes = {choice for choice, _ in CausalMode.choices}
    for rule, evaluated, effective_utility, _state in rows:
        if effective_utility <= 0:
            continue
        attribution = rule.attribution or {}
        strategy = attribution.get("strategy", "signal_contributors")
        if strategy == "unattributed":
            continue
        fraction = max(Decimal("0"), min(Decimal("1"), decimal_value(attribution.get("recognized_fraction", 1))))
        contributors = []
        for contributor in evaluated.attribution_shares:
            if not isinstance(contributor, dict):
                continue
            subject_type = contributor.get("subject_type")
            subject_id = contributor.get("subject_id")
            if subject_type not in {"profile", "space"} or not subject_id:
                continue
            if strategy == "profile_only" and subject_type != "profile":
                continue
            if strategy == "space_only" and subject_type != "space":
                continue
            weight = max(Decimal("0"), decimal_value(contributor.get("weight", 1)))
            subject = _resolve_subject(subject_type, subject_id)
            if weight <= 0 or subject is None:
                continue
            mode = str(contributor.get("causal_mode", CausalMode.OPERATE))
            if mode not in allowed_modes:
                mode = CausalMode.OPERATE
            key = f"{subject_type}:{subject.pk}"
            subjects[key] = (subject_type, subject)
            contributors.append((key, mode, weight))
        total_weight = sum((weight for _key, _mode, weight in contributors), Decimal("0"))
        if total_weight <= 0 or fraction <= 0:
            continue
        attributable = effective_utility * fraction
        for key, mode, weight in contributors:
            amount = attributable * weight / total_weight
            subject_utility[key] += amount
            subject_modes[key][mode] += amount
    resolved = []
    for key in sorted(subject_utility):
        amount = subject_utility[key]
        if amount <= 0:
            continue
        subject_type, subject = subjects[key]
        dominant_mode = max(subject_modes[key].items(), key=lambda row: (row[1], row[0]))[0]
        resolved.append(
            ResolvedShare(
                share=AttributionShare(
                    share=min(Decimal("1"), amount / total_utility),
                    profile=subject if subject_type == "profile" else None,
                    space=subject if subject_type == "space" else None,
                    description="Valeur rendue possible dans Makolo",
                ),
                causal_mode=dominant_mode,
                strength=amount,
            )
        )
    return tuple(resolved)


@transaction.atomic
def process_signal_group(*, signals, window, policy):
    signals = tuple(signals)
    if not signals:
        return 0
    facts = tuple(signal_fact(signal) for signal in signals)
    object_type = signals[0].object_type
    object_id = signals[0].object_id
    if any(signal.object_type != object_type or signal.object_id != object_id for signal in signals):
        raise ValueError("Recognition process_signal_group requires one object identity.")

    parameters = policy.parameters or {}
    semantic_window_hours = max(
        1,
        min(
            int(parameters.get("semantic_window_hours", policy.standard_window_hours) or policy.standard_window_hours),
            8760,
        ),
    )
    rules = list(
        policy.rules.filter(enabled=True, signal_kind__in={signal.signal_kind for signal in signals})
        .order_by("priority", "code")
    )
    group_identity = f"{object_type}:{object_id}:{window.starts_at.isoformat()}:{window.ends_at.isoformat()}"
    previous_states = _previous_rule_states(
        object_type=object_type,
        object_id=object_id,
        policy_version=policy.version_key,
    )
    rule_states = dict(previous_states)
    candidates = []
    rule_results = []

    for rule in rules:
        evaluated = evaluate_rule_group(
            signals=facts,
            rule=rule_spec(rule),
            parameters=parameters,
            policy_version=policy.version_key,
            group_identity=group_identity,
            semantic_window_hours=semantic_window_hours,
        )
        if evaluated is None:
            continue
        delta, state_after = _temporal_delta(
            rule=rule,
            evaluated=evaluated,
            prior_state=previous_states.get(rule.code),
        )
        rule_states[rule.code] = state_after
        if _has_resolvable_contributor(rule, evaluated):
            candidates.append((rule, evaluated, delta, state_after))
        rule_results.append({
            "rule": rule.code,
            "channel": rule.channel,
            "temporal_profile": rule.temporal_profile,
            "effective_utility": str(delta),
            "aggregation": rule.aggregation,
        })

    if not rule_results:
        RecognitionSignal.objects.filter(
            pk__in=[signal.pk for signal in signals],
            processed_at__isnull=True,
        ).update(processed_at=timezone.now())
        return 0

    selected = _select_combined(candidates)
    total_utility = sum((row[2] for row in selected), Decimal("0"))
    resolved = _resolve_object_shares(selected, total_utility)
    occurred_at = min(signal.occurred_at for signal in signals)
    available_at = max(signal.available_at for signal in signals)
    identity = (
        f"{policy.version_key}|object|{object_type}|{object_id}|"
        f"{window.starts_at.isoformat()}|{window.ends_at.isoformat()}"
    )
    explanation = {
        "object_type": object_type,
        "object_id": object_id,
        "rule_results": rule_results,
        "rule_states": rule_states,
        "utility_delta": str(total_utility),
        "channels": sorted({row[0].channel for row in selected if row[2] > 0}),
        "signal_ids": [signal.signal_id for signal in signals],
        "outcomes": [signal.outcome_identity for signal in signals],
        "earning_policy_version": policy.version_key,
        "observation_policy_version": window.policy_version,
    }
    result = process_impact_slice(
        window=window,
        slice_key="recognition-object:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        accrual_key=f"object:{object_type}:{object_id}:utility",
        channel=ImpactChannel.UTILITY.value,
        temporal_profile=TemporalProfile.FLOW.value,
        occurred_at=occurred_at,
        available_at=available_at,
        impact_delta=total_utility,
        attribution_shares=[item.share for item in resolved],
        points_target_for_cumulative=_points_target(policy),
        policy_version=policy.version_key,
        metadata=explanation,
        maturation_hours=int(parameters.get("maturation_hours", 0) or 0),
    )
    evaluation, _ = RecognitionObjectEvaluation.objects.get_or_create(
        receipt=result.receipt,
        defaults={
            "window": window,
            "rule": None,
            "object_type": object_type,
            "object_id": object_id,
            "utility_delta": total_utility,
            "pool_points": result.receipt.pool_points,
            "unattributed_points": result.receipt.unattributed_points,
            "explanation": explanation,
        },
    )
    by_subject = {item.share.subject_key(): item for item in resolved}
    for entry in result.grants:
        key = f"profile:{entry.account.profile_id}" if entry.account.profile_id else f"space:{entry.account.space_id}"
        detail = by_subject.get(key)
        RecognitionAllocation.objects.get_or_create(
            evaluation=evaluation,
            account=entry.account,
            causal_mode=(detail.causal_mode if detail else CausalMode.OPERATE),
            defaults={
                "causal_strength": detail.strength if detail else Decimal("1"),
                "share": detail.share.share if detail else Decimal("0"),
                "points": entry.points,
                "evidence": {
                    "signal_ids": explanation["signal_ids"],
                    "outcomes": explanation["outcomes"],
                },
            },
        )
        if entry.kind == RecognitionLedgerKind.GRANT.value:
            entry.account.refresh_from_db()
            grant_due_achievements(account=entry.account, evaluation=evaluation)
    RecognitionSignal.objects.filter(
        pk__in=[signal.pk for signal in signals],
        processed_at__isnull=True,
    ).update(processed_at=timezone.now())
    return int(result.created)


def run_default_recognition_cycle(*, now=None, max_windows=7):
    from .services import complete_window, ensure_cursor, get_due_window, mark_window_running

    now = now or timezone.now()
    released_points = release_due_pending_grants(now=now)
    cursor = RecognitionCursor.objects.filter(pk="recognition-v1").first()
    policy = activate_due_policy(now=now, cursor=cursor)
    if policy is None:
        return {
            "status": "no_active_policy",
            "processed_slices": 0,
            "issued_points": 0,
            "released_points": released_points,
        }
    window_hours = policy.standard_window_hours
    if cursor and cursor.policy_version != policy.version_key:
        if cursor.evaluation_windows.exclude(status=RecognitionWindowStatus.COMPLETED.value).exists():
            return {
                "status": "policy_transition_waiting",
                "processed_slices": 0,
                "issued_points": 0,
                "released_points": released_points,
            }
        cursor.policy_version = policy.version_key
        cursor.window_size_hours = window_hours
        cursor.save(update_fields=["policy_version", "window_size_hours", "updated_at"])
    cursor = ensure_cursor(
        key="recognition-v1",
        policy_version=policy.version_key,
        window_size_hours=window_hours,
        start_at=now - timedelta(hours=window_hours),
    )
    total_slices = total_points = windows = 0
    for _ in range(max(int(max_windows), 1)):
        window = get_due_window(cursor=cursor, now=now)
        if window is None:
            break
        mark_window_running(window)
        pending = list(signal_provider(window.starts_at, window.ends_at))
        by_policy_object = defaultdict(list)
        policies = {}
        for signal in pending:
            earning_policy = policy_for_fact(at=signal.occurred_at)
            if earning_policy is None:
                raise ValidationError(
                    f"Aucune Policy Recognition publiée ne couvre le fait {signal.signal_id} à {signal.occurred_at.isoformat()}."
                )
            policies[earning_policy.pk] = earning_policy
            by_policy_object[(earning_policy.pk, signal.object_type, signal.object_id)].append(signal)
        for (policy_id, _object_type, _object_id), group in by_policy_object.items():
            total_slices += process_signal_group(
                signals=group,
                window=window,
                policy=policies[policy_id],
            )
        window = complete_window(window=window, cursor=cursor)
        total_points += window.issued_points
        windows += 1
        cursor.refresh_from_db()
        next_policy = activate_due_policy(now=now, cursor=cursor)
        if next_policy and next_policy.version_key != cursor.policy_version:
            cursor.policy_version = next_policy.version_key
            cursor.window_size_hours = next_policy.standard_window_hours
            cursor.save(update_fields=["policy_version", "window_size_hours", "updated_at"])
            policy = next_policy
    released_points += release_due_pending_grants(now=now)
    return {
        "status": "ok",
        "windows": windows,
        "processed_slices": total_slices,
        "issued_points": total_points,
        "released_points": released_points,
    }
