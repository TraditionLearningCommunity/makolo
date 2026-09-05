from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can, has_platform_authority
from domain_events.contracts import DomainEventType

from .models import PaymentObligation, PaymentObligationStatus
from .obligation_services import _emit_obligation_event, _save_obligation_status


def _require_financial_manager(actor, obligation):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Une autorité financière explicite est requise.")
    if has_platform_authority(actor):
        return
    if obligation.payee_platform:
        raise PermissionDenied("Une autorité plateforme explicite est requise.")
    if obligation.payee_space_id and can(actor, PermissionCode.FINANCE_MANAGE, obligation.payee_space):
        return
    if obligation.journey_id:
        activity = obligation.journey.activity
        if activity.space_id and can(actor, PermissionCode.FINANCE_MANAGE, activity.space):
            return
        if can(actor, PermissionCode.ACTIVITY_FINANCE_MANAGE, activity=activity):
            return
    raise PermissionDenied("Une autorité financière explicite est requise.")


@transaction.atomic
def waive_payment_obligation(*, obligation, actor):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related(
        "journey__activity__space", "payee_space"
    ).get(pk=obligation.pk)
    _require_financial_manager(actor, obligation)
    if obligation.status == PaymentObligationStatus.WAIVED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être dispensée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.WAIVED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_WAIVED, "waived")
    return obligation


@transaction.atomic
def expire_payment_obligation(*, obligation, actor):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related(
        "journey__activity__space", "payee_space"
    ).get(pk=obligation.pk)
    _require_financial_manager(actor, obligation)
    if obligation.status == PaymentObligationStatus.EXPIRED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être expirée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.EXPIRED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_EXPIRED, "expired")
    return obligation


@transaction.atomic
def cancel_payment_obligation(*, obligation, actor):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related(
        "journey__activity__space", "payee_space"
    ).get(pk=obligation.pk)
    _require_financial_manager(actor, obligation)
    if obligation.status == PaymentObligationStatus.CANCELLED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être annulée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.CANCELLED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_CANCELLED, "cancelled")
    return obligation
