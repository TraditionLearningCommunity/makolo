from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from domain_events.contracts import DomainEventType

from .models import PaymentObligation, PaymentObligationStatus
from .obligation_services import _emit_obligation_event, _save_obligation_status


def _require_financial_manager(actor):
    # The final Services finance permission is intentionally deferred to T34.
    # Until then these sensitive administrative transitions are deny-by-default
    # outside explicit staff authority.
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_staff", False):
        raise PermissionDenied("Une autorité financière explicite est requise.")


@transaction.atomic
def waive_payment_obligation(*, obligation, actor):
    _require_financial_manager(actor)
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.WAIVED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être dispensée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.WAIVED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_WAIVED, "waived")
    return obligation


@transaction.atomic
def expire_payment_obligation(*, obligation, actor):
    _require_financial_manager(actor)
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.EXPIRED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être expirée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.EXPIRED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_EXPIRED, "expired")
    return obligation


@transaction.atomic
def cancel_payment_obligation(*, obligation, actor):
    _require_financial_manager(actor)
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.CANCELLED:
        return obligation
    if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
        raise ValidationError("Cette obligation ne peut plus être annulée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.CANCELLED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_CANCELLED, "cancelled")
    return obligation
