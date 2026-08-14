from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .models import (
    Journey,
    JourneyRequest,
    JourneyStatus,
    JourneyTransition,
    RequestPurpose,
    RequestStatus,
    TERMINAL_JOURNEY_STATUSES,
    WorkflowKind,
)


APPROVAL_WORKFLOWS = {
    WorkflowKind.ORDER_APPROVAL,
    WorkflowKind.RESERVATION,
    WorkflowKind.REGISTRATION,
    WorkflowKind.INVITATION,
}


def _check_occurrence(activity, occurrence):
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError("L’Occurrence doit appartenir à la même Activity que la Démarche.")


def create_journey(
    *,
    initiated_by,
    beneficiary,
    activity,
    workflow,
    occurrence=None,
    expires_at=None,
    status=JourneyStatus.DRAFT,
) -> Journey:
    _check_occurrence(activity, occurrence)
    journey = Journey(
        initiated_by=initiated_by,
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        workflow=workflow,
        status=status,
        expires_at=expires_at,
    )
    journey.full_clean()
    journey.save()
    return journey


def _save_transition(journey, *, previous_status, new_status, actor=None, reason=""):
    journey._allow_status_transition = True
    journey.save()
    JourneyTransition.objects.create(
        journey=journey,
        from_status=previous_status,
        to_status=new_status,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=(reason or "")[:160],
    )
    return journey


def _transition_locked(journey, *, new_status, actor=None, reason=""):
    previous = journey.status
    if previous == new_status:
        return journey
    journey.status = new_status
    now = timezone.now()
    if new_status == JourneyStatus.SUBMITTED and journey.submitted_at is None:
        journey.submitted_at = now
    elif new_status == JourneyStatus.CONFIRMED and journey.confirmed_at is None:
        journey.confirmed_at = now
    elif new_status == JourneyStatus.FULFILLED and journey.fulfilled_at is None:
        journey.fulfilled_at = now
    elif new_status == JourneyStatus.CANCELLED and journey.cancelled_at is None:
        journey.cancelled_at = now
    return _save_transition(
        journey,
        previous_status=previous,
        new_status=new_status,
        actor=actor,
        reason=reason,
    )


def _locked(journey):
    return (
        Journey.objects.select_for_update(of=("self",))
        .select_related("activity", "occurrence", "beneficiary", "initiated_by")
        .order_by()
        .get(pk=journey.pk)
    )


@transaction.atomic
def submit_journey(*, journey, actor=None, reason="submit"):
    journey = _locked(journey)
    if journey.status != JourneyStatus.DRAFT or journey.workflow == WorkflowKind.PURCHASE:
        raise ValidationError("Cette Démarche ne peut pas être soumise depuis son état actuel.")
    return _transition_locked(journey, new_status=JourneyStatus.SUBMITTED, actor=actor, reason=reason)


@transaction.atomic
def request_approval(*, journey, actor=None, reason="approval_required"):
    journey = _locked(journey)
    if journey.workflow not in APPROVAL_WORKFLOWS or journey.status != JourneyStatus.SUBMITTED:
        raise ValidationError("Cette Démarche ne peut pas demander une approbation maintenant.")
    return _transition_locked(
        journey,
        new_status=JourneyStatus.PENDING_APPROVAL,
        actor=actor,
        reason=reason,
    )


def _ensure_decider(actor, journey):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Une autorité authentifiée est requise pour cette décision.")
    if not can(actor, PermissionCode.ACTIVITY_REQUESTS_DECIDE, activity=journey.activity):
        raise PermissionDenied("Vous ne pouvez pas décider les Demandes de cette Activity.")


@transaction.atomic
def approve_journey(*, journey, actor, reason="approved"):
    journey = _locked(journey)
    _ensure_decider(actor, journey)
    if journey.workflow not in APPROVAL_WORKFLOWS:
        raise ValidationError("Ce workflow ne comporte pas d’approbation.")
    if journey.status == JourneyStatus.SUBMITTED and journey.workflow == WorkflowKind.INVITATION:
        pass
    elif journey.status != JourneyStatus.PENDING_APPROVAL:
        raise ValidationError("Cette Démarche n’est pas en attente d’approbation.")
    return _transition_locked(journey, new_status=JourneyStatus.APPROVED, actor=actor, reason=reason)


@transaction.atomic
def reject_journey(*, journey, actor, reason="rejected"):
    journey = _locked(journey)
    _ensure_decider(actor, journey)
    if journey.status not in {JourneyStatus.PENDING_APPROVAL, JourneyStatus.SUBMITTED}:
        raise ValidationError("Cette Démarche ne peut pas être rejetée depuis son état actuel.")
    return _transition_locked(journey, new_status=JourneyStatus.REJECTED, actor=actor, reason=reason)


@transaction.atomic
def require_payment(*, journey, actor=None, reason="payment_required"):
    journey = _locked(journey)
    allowed = (
        journey.workflow == WorkflowKind.PURCHASE and journey.status == JourneyStatus.DRAFT
    ) or (
        journey.workflow == WorkflowKind.ORDER_APPROVAL and journey.status == JourneyStatus.APPROVED
    )
    if not allowed:
        raise ValidationError("Cette Démarche ne peut pas attendre un paiement depuis son état actuel.")
    return _transition_locked(
        journey,
        new_status=JourneyStatus.PENDING_PAYMENT,
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def confirm_journey(*, journey, actor=None, reason="confirmed"):
    journey = _locked(journey)
    allowed = False
    if journey.workflow == WorkflowKind.PURCHASE:
        allowed = journey.status in {JourneyStatus.DRAFT, JourneyStatus.PENDING_PAYMENT}
    elif journey.workflow == WorkflowKind.ORDER_APPROVAL:
        allowed = journey.status in {JourneyStatus.APPROVED, JourneyStatus.PENDING_PAYMENT}
    elif journey.workflow in {WorkflowKind.RESERVATION, WorkflowKind.REGISTRATION}:
        allowed = journey.status in {JourneyStatus.SUBMITTED, JourneyStatus.APPROVED}
    elif journey.workflow == WorkflowKind.INVITATION:
        allowed = journey.status == JourneyStatus.APPROVED
    if not allowed:
        raise ValidationError("Cette Démarche ne peut pas être confirmée depuis son état actuel.")
    return _transition_locked(journey, new_status=JourneyStatus.CONFIRMED, actor=actor, reason=reason)


@transaction.atomic
def fulfill_journey(*, journey, actor=None, reason="fulfilled"):
    journey = _locked(journey)
    if journey.status != JourneyStatus.CONFIRMED:
        raise ValidationError("Seule une Démarche confirmée peut être réalisée.")
    return _transition_locked(journey, new_status=JourneyStatus.FULFILLED, actor=actor, reason=reason)


@transaction.atomic
def cancel_journey(*, journey, actor=None, reason="cancelled"):
    journey = _locked(journey)
    if journey.status in TERMINAL_JOURNEY_STATUSES:
        if journey.status == JourneyStatus.CANCELLED:
            return journey
        raise ValidationError("Cette Démarche est déjà terminée et ne peut plus être annulée.")
    return _transition_locked(journey, new_status=JourneyStatus.CANCELLED, actor=actor, reason=reason)


@transaction.atomic
def expire_journey(*, journey, now=None, reason="expired"):
    now = now or timezone.now()
    journey = _locked(journey)
    if journey.status in TERMINAL_JOURNEY_STATUSES:
        return journey
    if journey.expires_at is None or journey.expires_at > now:
        return journey
    return _transition_locked(journey, new_status=JourneyStatus.EXPIRED, reason=reason)


def expire_due_journeys(*, now=None) -> int:
    now = now or timezone.now()
    ids = list(
        Journey.objects.filter(expires_at__lte=now)
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .values_list("pk", flat=True)
    )
    changed = 0
    for journey_id in ids:
        journey = Journey.objects.get(pk=journey_id)
        before = journey.status
        journey = expire_journey(journey=journey, now=now)
        changed += int(journey.status != before)
    return changed


@transaction.atomic
def create_request(
    *,
    journey,
    requester,
    purpose=RequestPurpose.APPROVAL,
    message="",
    expires_at=None,
) -> JourneyRequest:
    journey = _locked(journey)
    if journey.status == JourneyStatus.SUBMITTED:
        if journey.workflow not in APPROVAL_WORKFLOWS:
            raise ValidationError("Cette Démarche ne supporte pas de Demande d’approbation.")
        journey = _transition_locked(
            journey,
            new_status=JourneyStatus.PENDING_APPROVAL,
            actor=requester,
            reason="request_created",
        )
    elif journey.status != JourneyStatus.PENDING_APPROVAL:
        raise ValidationError("Une Demande ne peut être ouverte que pendant l’étape d’approbation.")
    request = JourneyRequest(
        journey=journey,
        requester=requester,
        purpose=purpose,
        message=message,
        expires_at=expires_at,
    )
    request.full_clean()
    request.save()
    return request


def _lock_request_and_journey(request):
    request_id = request.pk
    journey_id = JourneyRequest.objects.only("journey_id").get(pk=request_id).journey_id
    journey = (
        Journey.objects.select_for_update(of=("self",))
        .select_related("activity")
        .order_by()
        .get(pk=journey_id)
    )
    request = (
        JourneyRequest.objects.select_for_update(of=("self",))
        .select_related("requester", "decided_by")
        .order_by()
        .get(pk=request_id)
    )
    return request, journey


def _save_request_decision(request, *, status, actor=None, comment=""):
    request.status = status
    request.decided_by = actor if getattr(actor, "is_authenticated", False) else None
    request.decision_comment = comment or ""
    request.decided_at = timezone.now()
    request._allow_status_transition = True
    request.save()
    return request


@transaction.atomic
def approve_request(*, request, actor, comment=""):
    request, journey = _lock_request_and_journey(request)
    _ensure_decider(actor, journey)
    if request.status != RequestStatus.PENDING:
        raise ValidationError("Cette Demande a déjà été décidée.")
    if request.expires_at and timezone.now() >= request.expires_at:
        _save_request_decision(request, status=RequestStatus.EXPIRED, comment="expired before decision")
        if journey.status == JourneyStatus.PENDING_APPROVAL:
            _transition_locked(journey, new_status=JourneyStatus.EXPIRED, reason="request_expired")
        raise ValidationError("Cette Demande a expiré.")
    _save_request_decision(request, status=RequestStatus.APPROVED, actor=actor, comment=comment)
    if journey.status not in {JourneyStatus.PENDING_APPROVAL, JourneyStatus.SUBMITTED}:
        raise ValidationError("La Démarche n’est plus dans un état approuvable.")
    _transition_locked(journey, new_status=JourneyStatus.APPROVED, actor=actor, reason="request_approved")
    return request


@transaction.atomic
def reject_request(*, request, actor, comment=""):
    request, journey = _lock_request_and_journey(request)
    _ensure_decider(actor, journey)
    if request.status != RequestStatus.PENDING:
        raise ValidationError("Cette Demande a déjà été décidée.")
    _save_request_decision(request, status=RequestStatus.REJECTED, actor=actor, comment=comment)
    if journey.status in {JourneyStatus.PENDING_APPROVAL, JourneyStatus.SUBMITTED}:
        _transition_locked(journey, new_status=JourneyStatus.REJECTED, actor=actor, reason="request_rejected")
    return request


@transaction.atomic
def cancel_request(*, request, actor, comment=""):
    request, journey = _lock_request_and_journey(request)
    if request.status != RequestStatus.PENDING:
        raise ValidationError("Cette Demande n’est plus en attente.")
    is_requester = request.requester_id == getattr(actor, "pk", None)
    can_manage = getattr(actor, "is_authenticated", False) and can(
        actor,
        PermissionCode.ACTIVITY_REQUESTS_DECIDE,
        activity=journey.activity,
    )
    if not (is_requester or can_manage):
        raise PermissionDenied("Vous ne pouvez pas annuler cette Demande.")
    _save_request_decision(request, status=RequestStatus.CANCELLED, actor=actor, comment=comment)
    if journey.status == JourneyStatus.PENDING_APPROVAL and not JourneyRequest.objects.filter(
        journey=journey,
        status=RequestStatus.PENDING,
    ).exclude(pk=request.pk).exists():
        _transition_locked(journey, new_status=JourneyStatus.CANCELLED, actor=actor, reason="request_cancelled")
    return request


@transaction.atomic
def expire_request(*, request, now=None):
    now = now or timezone.now()
    request, journey = _lock_request_and_journey(request)
    if request.status != RequestStatus.PENDING:
        return request
    if request.expires_at is None or request.expires_at > now:
        return request
    _save_request_decision(request, status=RequestStatus.EXPIRED, comment="expired")
    if journey.status == JourneyStatus.PENDING_APPROVAL:
        _transition_locked(journey, new_status=JourneyStatus.EXPIRED, reason="request_expired")
    return request


def expire_due_requests(*, now=None) -> int:
    now = now or timezone.now()
    ids = list(
        JourneyRequest.objects.filter(status=RequestStatus.PENDING, expires_at__lte=now)
        .values_list("pk", flat=True)
    )
    changed = 0
    for request_id in ids:
        request = JourneyRequest.objects.get(pk=request_id)
        before = request.status
        request = expire_request(request=request, now=now)
        changed += int(request.status != before)
    return changed
