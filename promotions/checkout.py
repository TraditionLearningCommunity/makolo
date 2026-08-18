from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from commerce.models import CommerceOrder, CommerceOrderStatus
from payments.models import Payment
from tickets.models import TicketOrderStatus

from .canonical_models import CommercePromotionRedemption
from .canonical_services import (
    allocate_discount,
    create_commerce_redemption,
    quote_commerce_promotion,
)


@transaction.atomic
def create_order_with_promotion(
    *,
    buyer,
    event,
    customer_name,
    customer_email,
    selections,
    promotion_code="",
    hold_minutes=20,
):
    """Event vocabulary over the canonical Commerce Promotion checkout."""
    from tickets.services import create_order

    return create_order(
        buyer=buyer,
        event=event,
        customer_name=customer_name,
        customer_email=customer_email,
        selections=selections,
        promotion_code=(promotion_code or "").strip(),
        hold_minutes=hold_minutes,
    )


@transaction.atomic
def apply_code_to_pending_order(*, order, actor, promotion_code):
    """Apply an Offer-targeted canonical Promotion to a pending Event order."""
    from tickets.services import _confirm_locked_order

    order = (
        order.__class__.objects.select_for_update()
        .select_related("event__activity__space", "buyer", "commerce_order", "journey")
        .get(pk=order.pk)
    )
    if order.status != TicketOrderStatus.PENDING or order.is_expired:
        raise ValidationError("Seule une commande en attente et non expirée peut recevoir un code.")
    if order.buyer_id != getattr(actor, "pk", None) and not getattr(actor, "is_staff", False):
        raise PermissionDenied("Vous ne pouvez pas modifier cette commande.")
    if not order.commerce_order_id:
        raise ValidationError("Cette commande Event n’a pas de CommerceOrder canonique.")
    commerce_order = (
        CommerceOrder.objects.select_for_update(of=("self",))
        .select_related("buyer", "payee_space", "journey")
        .get(pk=order.commerce_order_id)
    )
    if commerce_order.status != CommerceOrderStatus.PENDING:
        raise ValidationError("La commande Commerce n’est plus en attente.")
    if CommercePromotionRedemption.objects.filter(commerce_order=commerce_order).exists():
        raise ValidationError("Une promotion est déjà appliquée à cette commande.")
    if Payment.objects.filter(commerce_order=commerce_order).exists():
        raise ValidationError("Le code doit être appliqué avant d'initialiser un paiement.")

    items = list(
        commerce_order.items.select_for_update(of=("self",))
        .select_related("offer", "beneficiary")
        .order_by("created_at", "id")
    )
    prepared = [
        (item.offer, item.quantity, item.beneficiary, item.line_subtotal, Decimal("0.00"))
        for item in items
    ]
    quote = quote_commerce_promotion(
        code_value=promotion_code,
        buyer=commerce_order.buyer,
        customer_email=order.customer_email,
        selections=[(item.offer, item.quantity) for item in items],
        subtotal_amount=commerce_order.subtotal,
        currency=commerce_order.currency,
        payee_space=commerce_order.payee_space,
        now=timezone.now(),
    )
    allocated = allocate_discount(prepared=prepared, quote=quote)
    by_offer = {offer.pk: discount for offer, _quantity, _beneficiary, _subtotal, discount in allocated}
    for item in items:
        item.discount_total = by_offer[item.offer_id]
        item.line_total = item.line_subtotal - item.discount_total
        item.save(update_fields=["discount_total", "line_total"])

    commerce_order.discount_total = quote["discount_amount"]
    commerce_order.total = quote["final_amount"]
    commerce_order.save(update_fields=["discount_total", "total", "updated_at"])
    create_commerce_redemption(order=commerce_order, quote=quote)
    order.total_amount = commerce_order.total
    order.save(update_fields=["total_amount", "updated_at"])

    if commerce_order.total == Decimal("0.00"):
        return _confirm_locked_order(order)
    return order
