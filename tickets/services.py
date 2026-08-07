from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.signing import BadSignature, Signer
from django.db import transaction
from django.utils import timezone

from events.models import Event, EventStatus
from events.permissions import user_can_manage_event

from .models import (
    QR_SIGNING_SALT,
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketOrderStatus,
    TicketStatus,
    TicketType,
)


def _validate_event_sales(event: Event) -> None:
    if event.status != EventStatus.PUBLISHED:
        raise ValidationError("Les billets ne peuvent être commandés que pour un événement publié.")
    if not event.is_registration_open:
        raise ValidationError("Les inscriptions ne sont pas ouvertes pour cet événement.")


def _lock_event_ticket_types(event: Event):
    return list(
        TicketType.objects.select_for_update()
        .filter(event=event)
        .select_related("event")
        .order_by("id")
    )


def _event_committed_quantity(ticket_types) -> int:
    return sum(t.reserved_quantity + t.issued_quantity for t in ticket_types)


def _issue_tickets_for_order(order: TicketOrder, ticket_types_by_id: dict) -> list[Ticket]:
    tickets = []
    for item in order.items.select_related("ticket_type").all():
        ticket_type = ticket_types_by_id[item.ticket_type_id]
        if ticket_type.reserved_quantity < item.quantity:
            raise ValidationError("Le stock réservé de la commande est incohérent.")

        ticket_type.reserved_quantity -= item.quantity
        ticket_type.issued_quantity += item.quantity
        ticket_type.save(update_fields=["reserved_quantity", "issued_quantity", "updated_at"])

        for _ in range(item.quantity):
            tickets.append(
                Ticket(
                    event=order.event,
                    ticket_type=ticket_type,
                    order=order,
                    owner=order.buyer,
                    holder_name=order.customer_name,
                    holder_email=order.customer_email,
                )
            )

    Ticket.objects.bulk_create(tickets)
    return tickets


@transaction.atomic
def create_order(
    *,
    buyer,
    event: Event,
    customer_name: str,
    customer_email: str,
    selections: list[tuple[TicketType, int]],
    hold_minutes: int = 20,
) -> TicketOrder:
    event = Event.objects.select_for_update().get(pk=event.pk)
    _validate_event_sales(event)

    if not selections:
        raise ValidationError("Sélectionnez au moins un type de billet.")

    locked_types = _lock_event_ticket_types(event)
    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}

    normalized = []
    total_quantity = 0
    currencies = set()
    total_amount = Decimal("0.00")

    for selected_type, raw_quantity in selections:
        ticket_type = types_by_id.get(selected_type.pk)
        if not ticket_type:
            raise ValidationError("Un type de billet n’appartient pas à cet événement.")

        quantity = int(raw_quantity)
        if quantity < ticket_type.min_per_order or quantity > ticket_type.max_per_order:
            raise ValidationError(
                f"{ticket_type.name}: quantité autorisée entre "
                f"{ticket_type.min_per_order} et {ticket_type.max_per_order}."
            )
        if not ticket_type.is_on_sale:
            raise ValidationError(f"{ticket_type.name} n’est pas disponible à la vente.")
        if ticket_type.available_quantity is not None:
            if quantity > ticket_type.available_quantity:
                raise ValidationError(f"Stock insuffisant pour {ticket_type.name}.")

        normalized.append((ticket_type, quantity))
        total_quantity += quantity
        currencies.add(ticket_type.currency)
        total_amount += ticket_type.price * quantity

    if len(currencies) != 1:
        raise ValidationError("Une commande ne peut pas mélanger plusieurs devises.")

    if event.capacity is not None:
        committed = _event_committed_quantity(locked_types)
        if committed + total_quantity > event.capacity:
            raise ValidationError("La capacité restante de l’événement est insuffisante.")

    currency = currencies.pop()
    order = TicketOrder.objects.create(
        event=event,
        buyer=buyer if getattr(buyer, "is_authenticated", False) else None,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip().lower(),
        total_amount=total_amount,
        currency=currency,
        expires_at=timezone.now() + timedelta(minutes=hold_minutes),
    )

    for ticket_type, quantity in normalized:
        TicketOrderItem.objects.create(
            order=order,
            ticket_type=ticket_type,
            quantity=quantity,
            unit_price=ticket_type.price,
        )
        ticket_type.reserved_quantity += quantity
        ticket_type.save(update_fields=["reserved_quantity", "updated_at"])

    if total_amount == 0:
        _confirm_locked_order(order, locked_types)

    return order


def _confirm_locked_order(order: TicketOrder, locked_types: list[TicketType]) -> TicketOrder:
    if order.status != TicketOrderStatus.PENDING:
        raise ValidationError("Seule une commande en attente peut être confirmée.")
    if order.is_expired:
        raise ValidationError("Cette commande a expiré.")

    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}
    _issue_tickets_for_order(order, types_by_id)
    order.status = TicketOrderStatus.CONFIRMED
    order.confirmed_at = timezone.now()
    order.expires_at = None
    order.save(update_fields=["status", "confirmed_at", "expires_at", "updated_at"])
    return order


@transaction.atomic
def confirm_order(*, order: TicketOrder, actor) -> TicketOrder:
    order = (
        TicketOrder.objects.select_for_update()
        .select_related("event", "event__organizer")
        .get(pk=order.pk)
    )
    if not user_can_manage_event(actor, order.event):
        raise PermissionDenied("Vous ne pouvez pas confirmer cette commande.")

    locked_types = _lock_event_ticket_types(order.event)
    return _confirm_locked_order(order, locked_types)


@transaction.atomic
def cancel_order(*, order: TicketOrder, actor) -> TicketOrder:
    order = (
        TicketOrder.objects.select_for_update()
        .select_related("event", "event__organizer", "buyer")
        .get(pk=order.pk)
    )
    can_manage = user_can_manage_event(actor, order.event)
    is_buyer = getattr(actor, "is_authenticated", False) and order.buyer_id == actor.pk
    if not (can_manage or is_buyer):
        raise PermissionDenied("Vous ne pouvez pas annuler cette commande.")

    if order.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        return order

    if order.status == TicketOrderStatus.CONFIRMED and not can_manage:
        raise PermissionDenied(
            "Une commande confirmée doit être annulée par l’organisateur ou le support."
        )

    if order.status == TicketOrderStatus.CONFIRMED and order.tickets.filter(
        status=TicketStatus.USED
    ).exists():
        raise ValidationError(
            "Une commande contenant un billet déjà utilisé ne peut pas être annulée."
        )

    locked_types = _lock_event_ticket_types(order.event)
    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}

    if order.status == TicketOrderStatus.PENDING:
        for item in order.items.all():
            ticket_type = types_by_id[item.ticket_type_id]
            ticket_type.reserved_quantity = max(
                ticket_type.reserved_quantity - item.quantity,
                0,
            )
            ticket_type.save(update_fields=["reserved_quantity", "updated_at"])
    elif order.status == TicketOrderStatus.CONFIRMED:
        for item in order.items.all():
            ticket_type = types_by_id[item.ticket_type_id]
            ticket_type.issued_quantity = max(
                ticket_type.issued_quantity - item.quantity,
                0,
            )
            ticket_type.save(update_fields=["issued_quantity", "updated_at"])
        order.tickets.filter(status=TicketStatus.VALID).update(
            status=TicketStatus.CANCELLED,
            cancelled_at=timezone.now(),
        )

    order.status = TicketOrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.expires_at = None
    order.save(update_fields=["status", "cancelled_at", "expires_at", "updated_at"])
    return order


@transaction.atomic
def expire_order(*, order: TicketOrder) -> TicketOrder:
    order = TicketOrder.objects.select_for_update().select_related("event").get(pk=order.pk)
    if order.status != TicketOrderStatus.PENDING or not order.is_expired:
        return order

    locked_types = _lock_event_ticket_types(order.event)
    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}
    for item in order.items.all():
        ticket_type = types_by_id[item.ticket_type_id]
        ticket_type.reserved_quantity = max(ticket_type.reserved_quantity - item.quantity, 0)
        ticket_type.save(update_fields=["reserved_quantity", "updated_at"])

    order.status = TicketOrderStatus.EXPIRED
    order.save(update_fields=["status", "updated_at"])
    return order


def validate_qr_token(token: str) -> Ticket:
    try:
        raw_code = Signer(salt=QR_SIGNING_SALT).unsign(token)
    except BadSignature as exc:
        raise ValidationError("QR code invalide.") from exc

    try:
        ticket = Ticket.objects.select_related("event", "ticket_type", "order").get(
            code=raw_code
        )
    except (Ticket.DoesNotExist, ValueError) as exc:
        raise ValidationError("Billet introuvable.") from exc

    if not ticket.is_valid:
        raise ValidationError("Ce billet n’est pas valide.")
    return ticket
