"""Recognition-owned, permissioned policy workflow for Makolo Platform.

Admin remains an emergency/technical fallback. Platform never performs raw policy
CRUD and never treats a simulation preview as publication.
"""
from datetime import timedelta
from math import ceil

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from operations.services import audit_action

from .models import PolicyStatus, RecognitionCursor, RecognitionPolicy
from .simulation import simulate_policy


def _require(actor, code):
    if not getattr(actor, "is_authenticated", False) or not can(actor, code):
        raise PermissionDenied("Autorité Recognition requise.")


def _boundary(*, cursor, target):
    if cursor is None:
        return target
    window = timedelta(hours=cursor.window_size_hours)
    if target <= cursor.last_completed_end:
        return cursor.last_completed_end + window
    steps = max(1, ceil((target - cursor.last_completed_end).total_seconds() / window.total_seconds()))
    return cursor.last_completed_end + window * steps


def _reason(value):
    result = (value or "").strip()
    if not 5 <= len(result) <= 2000:
        raise ValidationError("Une raison explicite de 5 à 2000 caractères est obligatoire.")
    return result


@transaction.atomic
def record_policy_simulation(*, actor, policy_id, expected_status, reason):
    _require(actor, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE)
    reason = _reason(reason)
    policy = RecognitionPolicy.objects.select_for_update().get(pk=policy_id)
    if policy.status != expected_status or policy.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
        raise ValidationError("Cette Policy a changé ; actualisez-la avant de simuler.")
    now = timezone.now()
    snapshot = simulate_policy(policy=policy, starts_at=now - timedelta(days=30), ends_at=now)
    # The simulation is a preview, never a publication. Record the eligible state
    # only after the full owner simulation succeeds.
    RecognitionPolicy.objects.filter(pk=policy.pk).update(status=PolicyStatus.SIMULATED)
    audit_action(
        actor=actor, action="recognition.policy_simulated",
        target_type="recognition_policy", target_id=policy.pk,
        summary=f"Simulation de {policy.version_key} enregistrée",
        before={"status": expected_status},
        after={"status": PolicyStatus.SIMULATED, "signals": snapshot["signals"], "projected_credits": snapshot["projected_credits"]},
        metadata={"reason": reason, "window_days": 30},
    )
    return snapshot


@transaction.atomic
def publish_policy_for_actor(*, actor, policy_id, expected_status, reason):
    _require(actor, PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH)
    reason = _reason(reason)
    # Serialise competing publications for all Recognition policies.
    list(RecognitionPolicy.objects.order_by("pk").select_for_update().values_list("pk", flat=True))
    policy = RecognitionPolicy.objects.get(pk=policy_id)
    if policy.status != expected_status or policy.status != PolicyStatus.SIMULATED:
        raise ValidationError("Cette Policy doit être simulée et son état vérifié avant publication.")
    now = timezone.now()
    cursor = RecognitionCursor.objects.select_for_update().filter(pk="recognition-v1").first()
    desired = policy.effective_from or now
    old_status = policy.status
    if cursor is not None:
        effective_from = _boundary(cursor=cursor, target=max(now, desired))
        next_status = PolicyStatus.SCHEDULED
    elif desired > now:
        effective_from = desired
        next_status = PolicyStatus.SCHEDULED
    else:
        effective_from = now
        next_status = PolicyStatus.ACTIVE

    if next_status == PolicyStatus.ACTIVE:
        RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).exclude(pk=policy.pk).update(
            status=PolicyStatus.SUPERSEDED, effective_until=now
        )
    RecognitionPolicy.objects.filter(pk=policy.pk).update(
        status=next_status, effective_from=effective_from
    )
    audit_action(
        actor=actor, action="recognition.policy_published" if next_status == PolicyStatus.ACTIVE else "recognition.policy_scheduled",
        target_type="recognition_policy", target_id=policy.pk,
        summary=f"Recognition {policy.version_key} : {next_status}",
        before={"status": old_status, "effective_from": policy.effective_from.isoformat() if policy.effective_from else None},
        after={"status": next_status, "effective_from": effective_from.isoformat()},
        metadata={"reason": reason},
    )
    return {"status": next_status, "effective_from": effective_from}
