import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.signing import BadSignature, Signer
from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import AccessStatus, CredentialStatus
from access.services import resolve_access_credential
from events.models import Event, EventStatus
from events.permissions import user_can_manage_event, user_can_manage_event_finance

from .models import (
    QR_SIGNING_SALT,
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)


User = get_user_model()
WAITLIST_OFFER_MINUTES = 20
TRANSFER_EXPIRY_HOURS = 48


def _validate_event_sales(event: Event) -> None:
    if event.status != EventStatus.PUBLISHED:
        raise ValidationError("Les billets ne peuvent être commandés que pour un événement publié.")
    if not event.is_registration_open:
        raise ValidationError("Les inscriptions ne sont pas ouvertes pour cet événement.")


def _lock_event_ticket_types(event: Event):
    return list(
        TicketType.objects.select_for_update(of=("self",))
        .filter(event=event)
        .select_related("event")
        .order_by("id")
    )


def _event_committed_quantity(ticket_types) -> int:
    return sum(t.reserved_quantity + t.issued_quantity for t in ticket_types)


def _event_capacity_available(event: Event, ticket_types) -> int | None:
    if event.capacity is None:
        return None
    return max(event.capacity - _event_committed_quantity(ticket_types), 0)


def _available_for_ticket_type(ticket_type: TicketType, ticket_types) -> int | None:
    type_available = ticket_type.available_quantity
    capacity_available = _event_capacity_available(ticket_type.event, ticket_types)
    if type_available is None:
        return capacity_available
    if capacity_available is None:
        return type_available
    return min(type_available, capacity_available)


def _ticket_sales_window_open(ticket_type: TicketType, *, now=None) -> bool:
    now = now or timezone.now()
    event = ticket_type.event
    if not ticket_type.is_active or event.status != EventStatus.PUBLISHED:
        return False
    if not event.is_registration_open:
        return False
    if ticket_type.sales_start_at and now < ticket_type.sales_start_at:
        return False
    if ticket_type.sales_end_at and now > ticket_type.sales_end_at:
        return False
    return True


def can_join_waitlist(user, ticket_type: TicketType) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not _ticket_sales_window_open(ticket_type):
        return False
    ticket_types = list(TicketType.objects.filter(event=ticket_type.event).order_by("id"))
    current = next((item for item in ticket_types if item.pk == ticket_type.pk), ticket_type)
    available = _available_for_ticket_type(current, ticket_types)
    if available is None or available > 0:
        return False
    return not TicketWaitlistEntry.objects.filter(
        ticket_type=ticket_type,
        user=user,
        status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
    ).exists()


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
        if ticket_type.available_quantity is not None and quantity > ticket_type.available_quantity:
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

    TicketWaitlistEntry.objects.filter(
        offered_order=order,
        status=WaitlistStatus.OFFERED,
    ).update(
        status=WaitlistStatus.CONVERTED,
        converted_at=timezone.now(),
        updated_at=timezone.now(),
    )
    return order


@transaction.atomic
def confirm_order(*, order: TicketOrder, actor) -> TicketOrder:
    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related("event", "event__organizer")
        .get(pk=order.pk)
    )
    if not user_can_manage_event(actor, order.event):
        raise PermissionDenied("Vous ne pouvez pas confirmer cette commande.")

    locked_types = _lock_event_ticket_types(order.event)
    return _confirm_locked_order(order, locked_types)


def _schedule_waitlist_promotion(ticket_type_ids):
    unique_ids = tuple(dict.fromkeys(ticket_type_ids))
    for ticket_type_id in unique_ids:
        transaction.on_commit(
            lambda ticket_type_id=ticket_type_id: promote_waitlist_for_ticket_type(ticket_type_id)
        )


@transaction.atomic
def cancel_order(*, order: TicketOrder, actor) -> TicketOrder:
    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related("event", "event__organizer", "event__organization", "buyer")
        .get(pk=order.pk)
    )
    can_manage = user_can_manage_event(actor, order.event) or user_can_manage_event_finance(
        actor, order.event
    )
    is_buyer = getattr(actor, "is_authenticated", False) and order.buyer_id == actor.pk
    if not (can_manage or is_buyer):
        raise PermissionDenied("Vous ne pouvez pas annuler cette commande.")

    if order.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        return order

    if order.status == TicketOrderStatus.CONFIRMED and not can_manage:
        raise PermissionDenied(
            "Une commande confirmée doit être annulée par l'équipe autorisée ou le support."
        )

    if order.status == TicketOrderStatus.CONFIRMED and order.tickets.filter(
        status=TicketStatus.USED
    ).exists():
        raise ValidationError(
            "Une commande contenant un billet déjà utilisé ne peut pas être annulée."
        )

    locked_types = _lock_event_ticket_types(order.event)
    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}
    affected_type_ids = []

    if order.status == TicketOrderStatus.PENDING:
        for item in order.items.all():
            ticket_type = types_by_id[item.ticket_type_id]
            affected_type_ids.append(ticket_type.pk)
            ticket_type.reserved_quantity = max(ticket_type.reserved_quantity - item.quantity, 0)
            ticket_type.save(update_fields=["reserved_quantity", "updated_at"])
        TicketWaitlistEntry.objects.filter(
            offered_order=order,
            status=WaitlistStatus.OFFERED,
        ).update(
            status=WaitlistStatus.CANCELLED,
            cancelled_at=timezone.now(),
            updated_at=timezone.now(),
        )
    elif order.status == TicketOrderStatus.CONFIRMED:
        for item in order.items.all():
            ticket_type = types_by_id[item.ticket_type_id]
            affected_type_ids.append(ticket_type.pk)
            ticket_type.issued_quantity = max(ticket_type.issued_quantity - item.quantity, 0)
            ticket_type.save(update_fields=["issued_quantity", "updated_at"])
        order.tickets.filter(status=TicketStatus.VALID).update(
            status=TicketStatus.CANCELLED,
            cancelled_at=timezone.now(),
        )

    order.status = TicketOrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.expires_at = None
    order.save(update_fields=["status", "cancelled_at", "expires_at", "updated_at"])
    _schedule_waitlist_promotion(affected_type_ids)
    return order


@transaction.atomic
def expire_order(*, order: TicketOrder) -> TicketOrder:
    order = TicketOrder.objects.select_for_update(of=("self",)).select_related("event").get(pk=order.pk)
    if order.status != TicketOrderStatus.PENDING or not order.is_expired:
        return order

    locked_types = _lock_event_ticket_types(order.event)
    types_by_id = {ticket_type.pk: ticket_type for ticket_type in locked_types}
    affected_type_ids = []
    for item in order.items.all():
        ticket_type = types_by_id[item.ticket_type_id]
        affected_type_ids.append(ticket_type.pk)
        ticket_type.reserved_quantity = max(ticket_type.reserved_quantity - item.quantity, 0)
        ticket_type.save(update_fields=["reserved_quantity", "updated_at"])

    order.status = TicketOrderStatus.EXPIRED
    order.save(update_fields=["status", "updated_at"])
    TicketWaitlistEntry.objects.filter(
        offered_order=order,
        status=WaitlistStatus.OFFERED,
    ).update(status=WaitlistStatus.EXPIRED, updated_at=timezone.now())
    _schedule_waitlist_promotion(affected_type_ids)
    return order


@transaction.atomic
def join_waitlist(*, user, ticket_type: TicketType, quantity: int = 1) -> TicketWaitlistEntry:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour rejoindre la liste d’attente.")

    event = Event.objects.select_for_update().get(pk=ticket_type.event_id)
    locked_types = _lock_event_ticket_types(event)
    ticket_type = next((item for item in locked_types if item.pk == ticket_type.pk), None)
    if not ticket_type:
        raise ValidationError("Type de billet introuvable pour cet événement.")
    if not _ticket_sales_window_open(ticket_type):
        raise ValidationError("La liste d’attente n’est pas ouverte pour ce billet.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Quantité invalide.") from exc
    if quantity < ticket_type.min_per_order or quantity > ticket_type.max_per_order:
        raise ValidationError(
            f"Quantité autorisée entre {ticket_type.min_per_order} et {ticket_type.max_per_order}."
        )

    available = _available_for_ticket_type(ticket_type, locked_types)
    if available is None or available > 0:
        raise ValidationError("Des billets sont encore disponibles : réservez-les directement.")

    existing = TicketWaitlistEntry.objects.filter(
        ticket_type=ticket_type,
        user=user,
        status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
    ).first()
    if existing:
        return existing

    entry = TicketWaitlistEntry(
        ticket_type=ticket_type,
        user=user,
        requested_quantity=quantity,
    )
    entry.full_clean()
    try:
        entry.save()
    except IntegrityError:
        return TicketWaitlistEntry.objects.get(
            ticket_type=ticket_type,
            user=user,
            status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
        )
    return entry


def _waitlist_offer_expiry(ticket_type: TicketType, *, now, hold_minutes: int):
    candidates = [now + timedelta(minutes=hold_minutes), ticket_type.event.end_at]
    if ticket_type.event.registration_end_at:
        candidates.append(ticket_type.event.registration_end_at)
    if ticket_type.sales_end_at:
        candidates.append(ticket_type.sales_end_at)
    return min(candidates)


def _notify_waitlist_offer_on_commit(entry_id):
    from notifications.services import notify_waitlist_offer

    transaction.on_commit(lambda: notify_waitlist_offer(entry_id))


@transaction.atomic
def promote_waitlist_for_ticket_type(
    ticket_type_id,
    *,
    now=None,
    hold_minutes: int = WAITLIST_OFFER_MINUTES,
) -> int:
    now = now or timezone.now()
    initial = TicketType.objects.select_related("event").filter(pk=ticket_type_id).first()
    if not initial:
        return 0

    event = Event.objects.select_for_update().get(pk=initial.event_id)
    locked_types = _lock_event_ticket_types(event)
    ticket_type = next((item for item in locked_types if item.pk == initial.pk), None)
    if not ticket_type or not _ticket_sales_window_open(ticket_type, now=now):
        return 0

    available = _available_for_ticket_type(ticket_type, locked_types)
    if available is None or available <= 0:
        return 0

    entries = list(
        TicketWaitlistEntry.objects.select_for_update(of=("self",))
        .select_related("user")
        .filter(ticket_type=ticket_type, status=WaitlistStatus.WAITING)
        .order_by("created_at", "id")
    )
    promoted = 0
    for entry in entries:
        if entry.requested_quantity > available:
            break

        expires_at = _waitlist_offer_expiry(ticket_type, now=now, hold_minutes=hold_minutes)
        if expires_at <= now:
            break

        customer_name = entry.user.full_name or entry.user.username
        order = TicketOrder.objects.create(
            event=event,
            buyer=entry.user,
            customer_name=customer_name,
            customer_email=(entry.user.email or "").strip().lower(),
            total_amount=ticket_type.price * entry.requested_quantity,
            currency=ticket_type.currency,
            expires_at=expires_at,
        )
        TicketOrderItem.objects.create(
            order=order,
            ticket_type=ticket_type,
            quantity=entry.requested_quantity,
            unit_price=ticket_type.price,
        )
        ticket_type.reserved_quantity += entry.requested_quantity
        ticket_type.save(update_fields=["reserved_quantity", "updated_at"])

        entry.status = WaitlistStatus.OFFERED
        entry.offered_order = order
        entry.offered_at = now
        entry.offer_expires_at = expires_at
        entry.save(
            update_fields=[
                "status",
                "offered_order",
                "offered_at",
                "offer_expires_at",
                "updated_at",
            ]
        )
        _notify_waitlist_offer_on_commit(entry.pk)
        promoted += 1
        available -= entry.requested_quantity
        if available <= 0:
            break
    return promoted


def promote_open_waitlists(*, now=None) -> int:
    now = now or timezone.now()
    ticket_type_ids = list(
        TicketWaitlistEntry.objects.filter(
            status=WaitlistStatus.WAITING,
            ticket_type__event__status=EventStatus.PUBLISHED,
        )
        .values_list("ticket_type_id", flat=True)
        .distinct()
    )
    return sum(
        promote_waitlist_for_ticket_type(ticket_type_id, now=now)
        for ticket_type_id in ticket_type_ids
    )


@transaction.atomic
def accept_waitlist_offer(*, entry: TicketWaitlistEntry, user) -> TicketOrder:
    entry = (
        TicketWaitlistEntry.objects.select_for_update(of=("self",))
        .select_related("offered_order__event", "ticket_type", "user")
        .get(pk=entry.pk)
    )
    if entry.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Cette offre de liste d’attente ne vous appartient pas.")
    if entry.status != WaitlistStatus.OFFERED or not entry.offered_order_id:
        raise ValidationError("Cette offre n’est plus disponible.")

    order = TicketOrder.objects.select_for_update().get(pk=entry.offered_order_id)
    if order.is_expired or (entry.offer_expires_at and timezone.now() >= entry.offer_expires_at):
        expire_order(order=order)
        raise ValidationError("Cette offre a expiré.")

    if order.total_amount > 0:
        return order

    locked_types = _lock_event_ticket_types(order.event)
    _confirm_locked_order(order, locked_types)
    return order


@transaction.atomic
def leave_waitlist(*, entry: TicketWaitlistEntry, user) -> TicketWaitlistEntry:
    entry = (
        TicketWaitlistEntry.objects.select_for_update(of=("self",))
        .select_related("offered_order", "ticket_type")
        .get(pk=entry.pk)
    )
    if entry.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Cette entrée de liste d’attente ne vous appartient pas.")
    if entry.status not in {WaitlistStatus.WAITING, WaitlistStatus.OFFERED}:
        return entry

    if entry.status == WaitlistStatus.OFFERED and entry.offered_order_id:
        order = TicketOrder.objects.select_for_update().get(pk=entry.offered_order_id)
        if order.status == TicketOrderStatus.PENDING:
            cancel_order(order=order, actor=user)

    entry.status = WaitlistStatus.CANCELLED
    entry.cancelled_at = timezone.now()
    entry.save(update_fields=["status", "cancelled_at", "updated_at"])
    return entry


def _notify_transfer_created_on_commit(transfer_id):
    from notifications.services import notify_ticket_transfer_created

    transaction.on_commit(lambda: notify_ticket_transfer_created(transfer_id))


def _notify_transfer_accepted_on_commit(transfer_id):
    from notifications.services import notify_ticket_transfer_accepted

    transaction.on_commit(lambda: notify_ticket_transfer_accepted(transfer_id))


@transaction.atomic
def create_ticket_transfer(
    *,
    ticket: Ticket,
    sender,
    recipient_email: str,
    expiry_hours: int = TRANSFER_EXPIRY_HOURS,
) -> TicketTransfer:
    ticket = (
        Ticket.objects.select_for_update(of=("self",))
        .select_related("event", "owner", "ticket_type")
        .get(pk=ticket.pk)
    )
    if ticket.owner_id != getattr(sender, "pk", None):
        raise PermissionDenied("Seul le propriétaire actuel peut transférer ce billet.")
    if ticket.status != TicketStatus.VALID or not ticket.is_valid:
        raise ValidationError("Seul un billet valide et non utilisé peut être transféré.")

    recipient_email = (recipient_email or "").strip().lower()
    if not recipient_email:
        raise ValidationError("L’adresse e-mail du destinataire est obligatoire.")
    recipient = User.objects.filter(email__iexact=recipient_email, is_active=True).first()
    if not recipient:
        raise ValidationError(
            "Le destinataire doit déjà disposer d’un compte Makolo actif avec cette adresse e-mail."
        )
    if recipient.pk == sender.pk:
        raise ValidationError("Vous ne pouvez pas transférer un billet à vous-même.")

    if TicketTransfer.objects.filter(ticket=ticket, status=TransferStatus.PENDING).exists():
        raise ValidationError("Un transfert est déjà en attente pour ce billet.")

    now = timezone.now()
    expires_at = min(now + timedelta(hours=expiry_hours), ticket.event.end_at)
    if expires_at <= now:
        raise ValidationError("L’événement est trop proche ou déjà terminé pour ce transfert.")

    transfer = TicketTransfer(
        ticket=ticket,
        sender=sender,
        recipient=recipient,
        recipient_email=recipient.email.strip().lower(),
        expires_at=expires_at,
    )
    transfer.full_clean()
    try:
        transfer.save()
    except IntegrityError as exc:
        raise ValidationError("Un transfert est déjà en attente pour ce billet.") from exc
    _notify_transfer_created_on_commit(transfer.pk)
    return transfer


@transaction.atomic
def accept_ticket_transfer(*, transfer: TicketTransfer, recipient) -> TicketTransfer:
    transfer = (
        TicketTransfer.objects.select_for_update(of=("self",))
        .select_related("ticket__event", "ticket__owner", "sender", "recipient")
        .get(pk=transfer.pk)
    )
    if transfer.recipient_id != getattr(recipient, "pk", None):
        raise PermissionDenied("Ce transfert ne vous est pas destiné.")
    if transfer.status != TransferStatus.PENDING:
        raise ValidationError("Ce transfert n’est plus en attente.")

    now = timezone.now()
    if now >= transfer.expires_at:
        transfer.status = TransferStatus.EXPIRED
        transfer.expired_at = now
        transfer.save(update_fields=["status", "expired_at", "updated_at"])
        raise ValidationError("Ce transfert a expiré.")

    ticket = Ticket.objects.select_for_update(of=("self",)).select_related("event", "owner").get(pk=transfer.ticket_id)
    if ticket.owner_id != transfer.sender_id:
        raise ValidationError("Le propriétaire du billet a changé depuis la création du transfert.")
    if ticket.status != TicketStatus.VALID or not ticket.is_valid:
        raise ValidationError("Le billet n’est plus transférable.")

    ticket.code = uuid.uuid4()
    ticket.owner = recipient
    ticket.holder_name = recipient.full_name or recipient.username
    ticket.holder_email = (recipient.email or transfer.recipient_email).strip().lower()
    ticket.save(update_fields=["code", "owner", "holder_name", "holder_email", "updated_at"])

    transfer.status = TransferStatus.ACCEPTED
    transfer.accepted_at = now
    transfer.save(update_fields=["status", "accepted_at", "updated_at"])
    _notify_transfer_accepted_on_commit(transfer.pk)
    return transfer


@transaction.atomic
def decline_ticket_transfer(*, transfer: TicketTransfer, recipient) -> TicketTransfer:
    transfer = TicketTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.recipient_id != getattr(recipient, "pk", None):
        raise PermissionDenied("Ce transfert ne vous est pas destiné.")
    if transfer.status != TransferStatus.PENDING:
        return transfer
    transfer.status = TransferStatus.DECLINED
    transfer.declined_at = timezone.now()
    transfer.save(update_fields=["status", "declined_at", "updated_at"])
    return transfer


@transaction.atomic
def cancel_ticket_transfer(*, transfer: TicketTransfer, sender) -> TicketTransfer:
    transfer = TicketTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.sender_id != getattr(sender, "pk", None):
        raise PermissionDenied("Seul l’expéditeur peut annuler ce transfert.")
    if transfer.status != TransferStatus.PENDING:
        return transfer
    transfer.status = TransferStatus.CANCELLED
    transfer.cancelled_at = timezone.now()
    transfer.save(update_fields=["status", "cancelled_at", "updated_at"])
    return transfer


def expire_due_ticket_transfers(*, now=None) -> int:
    now = now or timezone.now()
    transfer_ids = list(
        TicketTransfer.objects.filter(
            status=TransferStatus.PENDING,
            expires_at__lte=now,
        ).values_list("pk", flat=True)
    )
    count = 0
    for transfer_id in transfer_ids:
        with transaction.atomic():
            transfer = TicketTransfer.objects.select_for_update().get(pk=transfer_id)
            if transfer.status != TransferStatus.PENDING or transfer.expires_at > now:
                continue
            transfer.status = TransferStatus.EXPIRED
            transfer.expired_at = now
            transfer.save(update_fields=["status", "expired_at", "updated_at"])
            count += 1
    return count


def _validate_canonical_ticket_qr(token: str) -> Ticket | None:
    try:
        credential = resolve_access_credential(token)
    except ValidationError:
        return None

    access = credential.access
    now = timezone.now()
    if credential.status != CredentialStatus.ACTIVE:
        raise ValidationError("Ce QR code n’est plus actif.")
    if access.status != AccessStatus.VALID:
        raise ValidationError("Ce billet n’est pas valide.")
    if access.valid_from and now < access.valid_from:
        raise ValidationError("Ce billet n’est pas encore valide.")
    if access.valid_until and now >= access.valid_until:
        raise ValidationError("Ce billet a expiré.")

    ticket = (
        Ticket.objects.select_related("event", "ticket_type", "order", "access")
        .filter(access=access)
        .first()
    )
    if ticket is None:
        raise ValidationError("Billet introuvable.")
    if not ticket.is_valid:
        raise ValidationError("Ce billet n’est pas valide.")
    return ticket


def validate_qr_token(token: str) -> Ticket:
    canonical = _validate_canonical_ticket_qr(token)
    if canonical is not None:
        return canonical

    try:
        raw_code = Signer(salt=QR_SIGNING_SALT).unsign(token)
    except BadSignature as exc:
        raise ValidationError("QR code invalide.") from exc

    try:
        ticket = Ticket.objects.select_related("event", "ticket_type", "order").get(code=raw_code)
    except (Ticket.DoesNotExist, ValueError) as exc:
        raise ValidationError("Billet introuvable.") from exc

    if not ticket.is_valid:
        raise ValidationError("Ce billet n’est pas valide.")
    return ticket