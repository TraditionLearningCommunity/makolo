from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import TicketOrderStatus

from .models import PromotionRedemption
from .services import create_redemption, quote_promotion


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
    """Crée la commande et applique le code dans une seule transaction.

    Si le code est invalide, la réservation de stock créée par `create_order`
    est annulée avec toute la transaction. Une remise qui ramène le total à
    zéro confirme immédiatement la commande et émet les billets.
    """
    from tickets.services import _confirm_locked_order, _lock_event_ticket_types, create_order

    order = create_order(
        buyer=buyer,
        event=event,
        customer_name=customer_name,
        customer_email=customer_email,
        selections=selections,
        hold_minutes=hold_minutes,
    )
    code_value = (promotion_code or "").strip()
    if not code_value:
        return order
    if order.status != TicketOrderStatus.PENDING:
        raise ValidationError("Un code promotionnel ne peut pas être appliqué à une commande déjà gratuite.")

    locked_order = (
        order.__class__.objects.select_for_update()
        .select_related("event", "event__organization", "buyer")
        .get(pk=order.pk)
    )
    item_rows = list(locked_order.items.select_related("ticket_type").all())
    normalized = [(item.ticket_type, item.quantity) for item in item_rows]
    subtotal = sum((item.unit_price * item.quantity for item in item_rows), Decimal("0.00"))
    quote = quote_promotion(
        code_value=code_value,
        event=locked_order.event,
        buyer=locked_order.buyer,
        customer_email=locked_order.customer_email,
        selections=normalized,
        subtotal_amount=subtotal,
        currency=locked_order.currency,
    )
    locked_order.total_amount = quote["final_amount"]
    locked_order.save(update_fields=["total_amount", "updated_at"])
    create_redemption(order=locked_order, quote=quote)

    if locked_order.total_amount == 0:
        locked_types = _lock_event_ticket_types(locked_order.event)
        _confirm_locked_order(locked_order, locked_types)
    return locked_order


@transaction.atomic
def apply_code_to_pending_order(*, order, actor, promotion_code):
    """Applique une offre à une commande encore en attente (ex. waitlist)."""
    from tickets.services import _confirm_locked_order, _lock_event_ticket_types

    order = (
        order.__class__.objects.select_for_update()
        .select_related("event", "event__organization", "buyer")
        .get(pk=order.pk)
    )
    if order.status != TicketOrderStatus.PENDING or order.is_expired:
        raise ValidationError("Seule une commande en attente et non expirée peut recevoir un code.")
    if order.buyer_id != getattr(actor, "pk", None) and not getattr(actor, "is_staff", False):
        raise PermissionDenied("Vous ne pouvez pas modifier cette commande.")
    if PromotionRedemption.objects.filter(order=order).exists():
        raise ValidationError("Une promotion est déjà appliquée à cette commande.")
    if order.payments.exists():
        raise ValidationError("Le code doit être appliqué avant d'initialiser un paiement.")

    item_rows = list(order.items.select_related("ticket_type").all())
    selections = [(item.ticket_type, item.quantity) for item in item_rows]
    subtotal = sum((item.unit_price * item.quantity for item in item_rows), Decimal("0.00"))
    quote = quote_promotion(
        code_value=promotion_code,
        event=order.event,
        buyer=order.buyer,
        customer_email=order.customer_email,
        selections=selections,
        subtotal_amount=subtotal,
        currency=order.currency,
        now=timezone.now(),
    )
    order.total_amount = quote["final_amount"]
    order.save(update_fields=["total_amount", "updated_at"])
    create_redemption(order=order, quote=quote)
    if order.total_amount == 0:
        _confirm_locked_order(order, _lock_event_ticket_types(order.event))
    return order
