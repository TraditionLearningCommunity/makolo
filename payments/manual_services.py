import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
from domain_events.contracts import DomainEventType

from .domain_events import emit_payment_domain_event
from .models import Payment, PaymentMethod, PaymentProvider, PaymentStatus


def can_record_manual_commerce_payment(actor, order):
    if not getattr(actor, "is_authenticated", False):
        return False
    if getattr(actor, "is_staff", False):
        return True
    activity = order.journey.activity
    space = order.payee_space or activity.space
    if space is not None and can(actor, PermissionCode.FINANCE_MANAGE, space):
        return True
    return can(actor, PermissionCode.ACTIVITY_FINANCE_MANAGE, activity=activity)


@transaction.atomic
def record_manual_commerce_payment(
    *,
    commerce_order,
    actor,
    method=PaymentMethod.CASH,
    provider_reference="",
    payer_name="",
    payer_email="",
    payer_phone="",
    idempotency_key=None,
):
    """Record money that was actually received outside an online provider.

    This never manufactures a Payment merely because an order is on-site. The
    caller is asserting a real collection event and must hold finance authority.
    """
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.commerce_order_id != commerce_order.pk:
                raise ValidationError("Cette clé d’idempotence appartient à une autre commande Commerce.")
            return existing

    order = (
        CommerceOrder.objects.select_for_update(of=("self",))
        .select_related("buyer", "journey__activity", "journey__activity__space", "payee_space", "payee_profile")
        .order_by()
        .get(pk=commerce_order.pk)
    )
    if not can_record_manual_commerce_payment(actor, order):
        raise PermissionDenied("Une autorité financière est requise pour enregistrer ce paiement manuel.")
    if order.status != CommerceOrderStatus.CONFIRMED:
        raise ValidationError("Le paiement manuel sur place exige une réservation confirmée.")
    if order.payment_mode not in {PaymentMode.ON_SITE, PaymentMode.LATER}:
        raise ValidationError("Cette commande n’attend pas un encaissement manuel différé.")
    if order.total <= 0:
        raise ValidationError("Une commande gratuite ne nécessite aucun paiement.")
    existing_success = Payment.objects.filter(commerce_order=order, status=PaymentStatus.SUCCEEDED).first()
    if existing_success:
        return existing_success
    if method not in PaymentMethod.values:
        raise ValidationError("Méthode de paiement manuelle invalide.")

    now = timezone.now()
    payment = Payment(
        commerce_order=order,
        initiated_by=actor,
        provider=PaymentProvider.MANUAL,
        method=method,
        status=PaymentStatus.SUCCEEDED,
        amount=order.total,
        currency=order.currency,
        payer_name=(payer_name or getattr(order.buyer, "full_name", "") or getattr(order.buyer, "username", "")).strip(),
        payer_email=(payer_email or getattr(order.buyer, "email", "")).strip().lower(),
        payer_phone=(payer_phone or "").strip(),
        provider_reference=(provider_reference or f"MAN-{uuid.uuid4().hex[:20].upper()}").strip(),
        idempotency_key=idempotency_key or None,
        processed_at=now,
        succeeded_at=now,
        metadata={"source": "manual-on-site"},
    )
    payment.full_clean()
    try:
        payment.save()
    except IntegrityError as exc:
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        existing = Payment.objects.filter(commerce_order=order, status=PaymentStatus.SUCCEEDED).first()
        if existing:
            return existing
        raise ValidationError("Impossible d’enregistrer ce paiement manuel de façon unique.") from exc
    emit_payment_domain_event(payment, event_type=DomainEventType.PAYMENT_SUCCEEDED)
    return payment
