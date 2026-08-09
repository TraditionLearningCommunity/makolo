from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from promotions.checkout import create_order_with_promotion
from tickets.models import TicketOrder


IDEMPOTENCY_CONFLICT_MESSAGE = (
    "Cette clé d’idempotence a déjà été utilisée pour une commande différente."
)


def _validate_existing(*, order, buyer, fingerprint):
    if order.buyer_id != getattr(buyer, "pk", None):
        raise ValidationError(IDEMPOTENCY_CONFLICT_MESSAGE)
    if not order.idempotency_fingerprint or order.idempotency_fingerprint != fingerprint:
        raise ValidationError(IDEMPOTENCY_CONFLICT_MESSAGE)
    order._idempotent_replay = True
    return order


def get_idempotent_order(*, idempotency_key, buyer, fingerprint):
    if not idempotency_key:
        return None
    existing = (
        TicketOrder.objects.select_related("event", "buyer")
        .prefetch_related("items__ticket_type", "tickets__ticket_type")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if not existing:
        return None
    return _validate_existing(order=existing, buyer=buyer, fingerprint=fingerprint)


def create_idempotent_order_with_promotion(
    *,
    buyer,
    event,
    customer_name,
    customer_email,
    selections,
    promotion_code="",
    idempotency_key=None,
    idempotency_fingerprint="",
):
    """Create one order for one client request, even across network retries.

    The existing ticket service remains the sole owner of stock/capacity/price
    validation and row locking. This outer transaction only binds the resulting
    order to the client key. On a concurrent duplicate, the database UNIQUE
    constraint rejects the second binding and the whole second stock reservation
    is rolled back before the already-created order is returned.
    """
    if not idempotency_key:
        order = create_order_with_promotion(
            buyer=buyer,
            event=event,
            customer_name=customer_name,
            customer_email=customer_email,
            selections=selections,
            promotion_code=promotion_code,
        )
        order._idempotent_replay = False
        return order

    existing = get_idempotent_order(
        idempotency_key=idempotency_key,
        buyer=buyer,
        fingerprint=idempotency_fingerprint,
    )
    if existing:
        return existing

    try:
        with transaction.atomic():
            existing = TicketOrder.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                return _validate_existing(
                    order=existing,
                    buyer=buyer,
                    fingerprint=idempotency_fingerprint,
                )

            order = create_order_with_promotion(
                buyer=buyer,
                event=event,
                customer_name=customer_name,
                customer_email=customer_email,
                selections=selections,
                promotion_code=promotion_code,
            )
            order.idempotency_key = idempotency_key
            order.idempotency_fingerprint = idempotency_fingerprint
            order.save(
                update_fields=[
                    "idempotency_key",
                    "idempotency_fingerprint",
                    "updated_at",
                ]
            )
            order._idempotent_replay = False
            return order
    except IntegrityError as exc:
        existing = TicketOrder.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if not existing:
            raise
        return _validate_existing(
            order=existing,
            buyer=buyer,
            fingerprint=idempotency_fingerprint,
        )
