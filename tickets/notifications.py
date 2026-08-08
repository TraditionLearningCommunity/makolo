from django.urls import reverse

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import TicketTransfer, TicketWaitlistEntry


def notify_waitlist_offer(entry_id):
    entry = (
        TicketWaitlistEntry.objects.select_related(
            "user",
            "ticket_type__event",
            "offered_order",
        )
        .filter(pk=entry_id)
        .first()
    )
    if not entry or not entry.offered_order_id:
        return None

    event = entry.ticket_type.event
    quantity = entry.requested_quantity
    return create_notification(
        recipient=entry.user,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.TICKET,
        title="Une place vient de se libérer",
        message=(
            f"Makolo vous réserve temporairement {quantity} place(s) « {entry.ticket_type.name} » "
            f"pour « {event.title} ». Finalisez la réservation avant l’expiration de l’offre."
        ),
        action_url=reverse("tickets:order-detail", kwargs={"pk": entry.offered_order_id}),
        dedup_key=f"waitlist-offer:{entry.pk}",
        metadata={
            "waitlist_entry_id": str(entry.pk),
            "order_id": str(entry.offered_order_id),
            "event_id": str(event.pk),
        },
    )


def notify_ticket_transfer_created(transfer_id):
    transfer = (
        TicketTransfer.objects.select_related(
            "recipient",
            "sender",
            "ticket__event",
            "ticket__ticket_type",
        )
        .filter(pk=transfer_id)
        .first()
    )
    if not transfer:
        return None

    return create_notification(
        recipient=transfer.recipient,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.TICKET,
        title="Un billet vous a été transféré",
        message=(
            f"{transfer.sender.full_name or transfer.sender.username} souhaite vous transférer "
            f"un billet « {transfer.ticket.ticket_type.name} » pour « {transfer.ticket.event.title} ». "
            "Acceptez-le dans Makolo pour recevoir un nouveau QR code."
        ),
        action_url=reverse("tickets:transfer-list"),
        dedup_key=f"ticket-transfer-created:{transfer.pk}",
        metadata={
            "transfer_id": str(transfer.pk),
            "ticket_id": str(transfer.ticket_id),
            "event_id": str(transfer.ticket.event_id),
        },
    )


def notify_ticket_transfer_accepted(transfer_id):
    transfer = (
        TicketTransfer.objects.select_related(
            "recipient",
            "sender",
            "ticket__event",
            "ticket__ticket_type",
        )
        .filter(pk=transfer_id)
        .first()
    )
    if not transfer:
        return None

    recipient_notification = create_notification(
        recipient=transfer.recipient,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.TICKET,
        title="Billet transféré avec succès",
        message=(
            f"Le billet « {transfer.ticket.ticket_type.name} » pour « {transfer.ticket.event.title} » "
            "est maintenant à votre nom. Makolo a généré un nouveau QR code et invalidé l’ancien."
        ),
        action_url=reverse("tickets:detail", kwargs={"pk": transfer.ticket_id}),
        dedup_key=f"ticket-transfer-accepted-recipient:{transfer.pk}",
        metadata={"transfer_id": str(transfer.pk), "ticket_id": str(transfer.ticket_id)},
    )

    create_notification(
        recipient=transfer.sender,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.TICKET,
        title="Votre transfert de billet a été accepté",
        message=(
            f"{transfer.recipient.full_name or transfer.recipient.username} a accepté le billet "
            f"pour « {transfer.ticket.event.title} ». Votre ancien QR code est définitivement invalide."
        ),
        action_url=reverse("tickets:transfer-list"),
        dedup_key=f"ticket-transfer-accepted-sender:{transfer.pk}",
        metadata={"transfer_id": str(transfer.pk), "ticket_id": str(transfer.ticket_id)},
    )
    return recipient_notification
