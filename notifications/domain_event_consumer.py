from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from access.models import Access
from activities.models import Activity, Occurrence
from commerce.models import PaymentMode
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from events.models import Event
from journeys.models import Journey, JourneyRequest, WorkflowKind
from payments.models import Payment
from tickets.models import Ticket

from .domain_event_selectors import occurrence_recipients
from .models import NotificationCategory, NotificationKind
from .services import create_notification


CONSUMER_NAME = "notifications.system"
SYSTEM_EVENT_TYPES = {
    DomainEventType.JOURNEY_CONFIRMED,
    DomainEventType.JOURNEY_PENDING_PAYMENT,
    DomainEventType.REQUEST_APPROVED,
    DomainEventType.ACCESS_ISSUED,
    DomainEventType.PAYMENT_SUCCEEDED,
    DomainEventType.PAYMENT_FAILED,
    DomainEventType.PAYMENT_REFUNDED,
    DomainEventType.OCCURRENCE_RESCHEDULED,
    DomainEventType.OCCURRENCE_CANCELLED,
}


def _legacy_event(activity):
    return Event.objects.filter(activity_id=activity.pk).first()


def _event_action(event):
    return reverse("events:detail", kwargs={"slug": event.slug}) if event else ""


def _domain_dedup(event, recipient, template_key):
    return f"domain:{event.pk}:{recipient.pk}:{template_key}"[:255]


def _journey_confirmation_copy(journey, commerce_order=None):
    activity = journey.activity
    event = _legacy_event(activity)
    subject = event.title if event else activity.title
    if commerce_order and commerce_order.payment_mode == PaymentMode.ON_SITE:
        return (
            "Réservation confirmée",
            f"Votre réservation pour « {subject} » est confirmée. Le paiement est prévu sur place.",
        )
    if journey.workflow == WorkflowKind.REGISTRATION:
        return "Inscription confirmée", f"Votre inscription à « {subject} » est confirmée."
    if journey.workflow == WorkflowKind.INVITATION:
        return "Invitation confirmée", f"Votre invitation pour « {subject} » est confirmée."
    if journey.workflow == WorkflowKind.RESERVATION:
        return "Réservation confirmée", f"Votre réservation pour « {subject} » est confirmée."
    return "Confirmation Makolo", f"Votre démarche pour « {subject} » est confirmée."


def _notify_journey_confirmed(domain_event):
    journey_id = domain_event.payload.get("journey_id")
    journey = (
        Journey.objects.select_related("beneficiary", "activity")
        .filter(pk=journey_id)
        .first()
    )
    if not journey or not journey.beneficiary_id:
        return
    legacy_event = _legacy_event(journey.activity)
    legacy_ticket_order = getattr(journey, "ticket_order", None)
    if legacy_event and legacy_ticket_order is not None:
        # The Event projection presents the resulting Access as Ticket; access.issued
        # creates the historical bundled ticket notification once the rights exist.
        return
    commerce_order = journey.commerce_orders.order_by("-created_at").first()
    title, message = _journey_confirmation_copy(journey, commerce_order)
    template_key = "journey.confirmed"
    create_notification(
        recipient=journey.beneficiary,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.EVENT if legacy_event else NotificationCategory.SYSTEM,
        title=title,
        message=message,
        action_url=_event_action(legacy_event),
        dedup_key=f"journey-confirmed:{journey.pk}:{journey.beneficiary_id}",
        metadata={"journey_id": str(journey.pk), "activity_id": str(journey.activity_id)},
        domain_event=domain_event,
        activity=journey.activity,
        journey=journey,
        commerce_order=commerce_order,
        template_key=template_key,
    )


def _notify_payment_required(domain_event):
    journey = (
        Journey.objects.select_related("beneficiary", "activity")
        .filter(pk=domain_event.payload.get("journey_id"))
        .first()
    )
    if not journey or not journey.beneficiary_id:
        return
    event = _legacy_event(journey.activity)
    subject = event.title if event else journey.activity.title
    order = journey.commerce_orders.order_by("-created_at").first()
    action_url = ""
    legacy_order = getattr(journey, "ticket_order", None)
    if legacy_order is not None:
        action_url = reverse("tickets:order-detail", kwargs={"pk": legacy_order.pk})
    template_key = "journey.payment.required"
    create_notification(
        recipient=journey.beneficiary,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.PAYMENT,
        title="Paiement requis",
        message=f"Votre demande pour « {subject} » est approuvée. Un paiement est requis pour finaliser la confirmation.",
        action_url=action_url,
        dedup_key=_domain_dedup(domain_event, journey.beneficiary, template_key),
        metadata={"journey_id": str(journey.pk), "activity_id": str(journey.activity_id)},
        domain_event=domain_event,
        activity=journey.activity,
        journey=journey,
        commerce_order=order,
        template_key=template_key,
    )


def _notify_request_approved(domain_event):
    request = (
        JourneyRequest.objects.select_related("requester", "journey__activity")
        .filter(pk=domain_event.payload.get("request_id"))
        .first()
    )
    if not request or not request.requester_id:
        return
    event = _legacy_event(request.journey.activity)
    subject = event.title if event else request.journey.activity.title
    template_key = "journey.request.approved"
    create_notification(
        recipient=request.requester,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.EVENT if event else NotificationCategory.SYSTEM,
        title="Demande approuvée",
        message=f"Votre demande pour « {subject} » a été approuvée.",
        action_url=_event_action(event),
        dedup_key=_domain_dedup(domain_event, request.requester, template_key),
        metadata={"request_id": str(request.pk), "journey_id": str(request.journey_id)},
        domain_event=domain_event,
        activity=request.journey.activity,
        journey=request.journey,
        template_key=template_key,
    )


def _notify_access_issued(domain_event):
    access = (
        Access.objects.select_related("beneficiary", "activity", "journey")
        .filter(pk=domain_event.payload.get("access_id"))
        .first()
    )
    if not access or not access.beneficiary_id:
        return
    ticket = Ticket.objects.select_related("order", "event").filter(access=access).first()
    if ticket:
        order = ticket.order
        quantity = order.tickets.count()
        template_key = "access.issued.ticket"
        create_notification(
            recipient=access.beneficiary,
            kind=NotificationKind.TICKETS_ISSUED,
            category=NotificationCategory.TICKET,
            title="Vos billets sont disponibles",
            message=(
                f"Votre commande {order.reference} pour « {ticket.event.title} » est confirmée. "
                f"{quantity} billet(s) sont maintenant disponibles avec leur QR code."
            ),
            action_url=reverse("tickets:order-detail", kwargs={"pk": order.pk}),
            dedup_key=f"order-confirmed:{order.pk}",
            metadata={"order_id": str(order.pk), "event_id": str(ticket.event_id), "access_id": str(access.pk)},
            domain_event=domain_event,
            activity=access.activity,
            journey=access.journey,
            access=access,
            commerce_order=getattr(order, "commerce_order", None),
            template_key=template_key,
        )
        return

    event = _legacy_event(access.activity)
    if access.journey_id:
        title, message = _journey_confirmation_copy(
            access.journey,
            access.journey.commerce_orders.order_by("-created_at").first(),
        )
        dedup_key = f"journey-confirmed:{access.journey_id}:{access.beneficiary_id}"
        template_key = "access.issued"
    else:
        subject = event.title if event else access.activity.title
        title = "Accès disponible"
        message = f"Votre accès pour « {subject} » est disponible."
        dedup_key = f"access-issued:{access.pk}:{access.beneficiary_id}"
        template_key = "access.issued"
    create_notification(
        recipient=access.beneficiary,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.EVENT if event else NotificationCategory.SYSTEM,
        title=title,
        message=message,
        action_url=_event_action(event),
        dedup_key=dedup_key,
        metadata={"access_id": str(access.pk), "activity_id": str(access.activity_id)},
        domain_event=domain_event,
        activity=access.activity,
        journey=access.journey,
        access=access,
        template_key=template_key,
    )


def _payment_recipient(payment):
    if payment.commerce_order_id:
        order = payment.commerce_order
        if order.buyer_id:
            return order.buyer
        if order.journey_id:
            return order.journey.beneficiary
    if payment.order_id and payment.order.buyer_id:
        return payment.order.buyer
    return None


def _payment_context(payment):
    if payment.order_id:
        event = payment.order.event
        activity = event.activity
        journey = payment.order.journey
        commerce_order = payment.commerce_order
        return event, activity, journey, commerce_order
    commerce_order = payment.commerce_order
    journey = commerce_order.journey if commerce_order else None
    activity = journey.activity if journey else None
    event = _legacy_event(activity) if activity else None
    return event, activity, journey, commerce_order


def _notify_payment(domain_event):
    payment = (
        Payment.objects.select_related(
            "order__buyer",
            "order__event__activity",
            "order__journey",
            "commerce_order__buyer",
            "commerce_order__journey__beneficiary",
            "commerce_order__journey__activity",
        )
        .filter(pk=domain_event.payload.get("payment_id"))
        .first()
    )
    if not payment:
        return
    recipient = _payment_recipient(payment)
    if recipient is None:
        return
    legacy_event, activity, journey, commerce_order = _payment_context(payment)
    subject = legacy_event.title if legacy_event else (activity.title if activity else "votre démarche")
    if domain_event.event_type == DomainEventType.PAYMENT_SUCCEEDED:
        kind = NotificationKind.PAYMENT_SUCCEEDED
        title = "Paiement confirmé"
        message = f"Le paiement {payment.reference} de {payment.amount} {payment.currency} pour « {subject} » a été confirmé."
        if legacy_event:
            message += " Vos billets sont disponibles."
        template_key = "payment.succeeded"
    elif domain_event.event_type == DomainEventType.PAYMENT_FAILED:
        kind = NotificationKind.PAYMENT_FAILED
        title = "Paiement non abouti"
        message = f"Le paiement {payment.reference} pour « {subject} » n’a pas abouti. Vous pouvez réessayer tant que votre démarche reste valide."
        template_key = "payment.failed"
    else:
        kind = NotificationKind.PAYMENT_REFUNDED
        title = "Paiement remboursé"
        message = f"Le paiement {payment.reference} de {payment.amount} {payment.currency} a été remboursé."
        if legacy_event:
            message += " Les billets associés à cette commande ont été annulés."
        template_key = "payment.refunded"
    action_url = reverse("payments:detail", kwargs={"pk": payment.pk}) if payment.order_id else ""
    create_notification(
        recipient=recipient,
        kind=kind,
        category=NotificationCategory.PAYMENT,
        title=title,
        message=message,
        action_url=action_url,
        dedup_key=f"payment-{domain_event.event_type.rsplit('.', 1)[-1]}:{payment.pk}",
        metadata={"payment_id": str(payment.pk), "commerce_order_id": str(payment.commerce_order_id) if payment.commerce_order_id else None},
        domain_event=domain_event,
        activity=activity,
        journey=journey,
        commerce_order=commerce_order,
        template_key=template_key,
    )


def _notify_occurrence(domain_event):
    occurrence = (
        Occurrence.objects.select_related("activity")
        .filter(pk=domain_event.payload.get("occurrence_id"))
        .first()
    )
    if not occurrence:
        return
    event = _legacy_event(occurrence.activity)
    subject = event.title if event else occurrence.activity.title
    if domain_event.event_type == DomainEventType.OCCURRENCE_RESCHEDULED:
        title = "Horaire modifié"
        starts = timezone.localtime(occurrence.start_at).strftime("%d/%m/%Y à %H:%M")
        message = f"L’horaire de « {subject} » a été modifié. Nouveau début : {starts}."
        template_key = "occurrence.rescheduled"
    else:
        title = "Activité annulée"
        message = f"« {subject} » a été annulé(e)."
        template_key = "occurrence.cancelled"
    for recipient in occurrence_recipients(occurrence):
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.EVENT if event else NotificationCategory.SYSTEM,
            title=title,
            message=message,
            action_url=_event_action(event),
            dedup_key=_domain_dedup(domain_event, recipient, template_key),
            metadata={"occurrence_id": str(occurrence.pk), "activity_id": str(occurrence.activity_id)},
            domain_event=domain_event,
            activity=occurrence.activity,
            template_key=template_key,
        )


def consume_system_notification_event(domain_event):
    handlers = {
        DomainEventType.JOURNEY_CONFIRMED: _notify_journey_confirmed,
        DomainEventType.JOURNEY_PENDING_PAYMENT: _notify_payment_required,
        DomainEventType.REQUEST_APPROVED: _notify_request_approved,
        DomainEventType.ACCESS_ISSUED: _notify_access_issued,
        DomainEventType.PAYMENT_SUCCEEDED: _notify_payment,
        DomainEventType.PAYMENT_FAILED: _notify_payment,
        DomainEventType.PAYMENT_REFUNDED: _notify_payment,
        DomainEventType.OCCURRENCE_RESCHEDULED: _notify_occurrence,
        DomainEventType.OCCURRENCE_CANCELLED: _notify_occurrence,
    }
    handler = handlers.get(domain_event.event_type)
    if handler:
        handler(domain_event)


register_consumer(
    CONSUMER_NAME,
    consume_system_notification_event,
    event_types=SYSTEM_EVENT_TYPES,
)
