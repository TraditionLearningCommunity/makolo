from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from access.models import Access
from activities.models import Activity, Occurrence
from commerce.models import PaymentMode
from core.product_language import occurrence_change_copy, vocabulary_for
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from journeys.models import Journey, JourneyRequest, WorkflowKind
from payments.models import Payment

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


def _domain_dedup(event, recipient, template_key):
    return f"domain:{event.pk}:{recipient.pk}:{template_key}"[:255]


def _category_for(activity):
    return (
        NotificationCategory.EVENT
        if vocabulary_for(activity=activity).vertical == "event"
        else NotificationCategory.SYSTEM
    )


def _journey_action(journey):
    return reverse("core:participant-journey-detail", kwargs={"pk": journey.pk})


def _access_action(access):
    return reverse("core:participant-access-detail", kwargs={"pk": access.pk})


def _journey_confirmation_copy(journey, commerce_order=None):
    subject = journey.activity.title
    vocabulary = vocabulary_for(activity=journey.activity, workflow=journey.workflow)
    if commerce_order and commerce_order.payment_mode == PaymentMode.ON_SITE:
        return (
            f"{vocabulary.journey_noun} confirmée",
            f"Votre {vocabulary.journey_noun.lower()} pour « {subject} » est confirmée. Le paiement est prévu sur place.",
        )
    if journey.workflow == WorkflowKind.REGISTRATION:
        return "Inscription confirmée", f"Votre inscription à « {subject} » est confirmée."
    if journey.workflow == WorkflowKind.INVITATION:
        return "Invitation confirmée", f"Votre invitation pour « {subject} » est confirmée."
    if journey.workflow == WorkflowKind.RESERVATION:
        return "Réservation confirmée", f"Votre réservation pour « {subject} » est confirmée."
    if journey.workflow == WorkflowKind.PURCHASE:
        return "Achat confirmé", f"Votre achat pour « {subject} » est confirmé."
    return "Confirmation Makolo", f"Votre démarche pour « {subject} » est confirmée."


def _notify_journey_confirmed(domain_event):
    journey = (
        Journey.objects.select_related("beneficiary", "activity")
        .filter(pk=domain_event.payload.get("journey_id"))
        .first()
    )
    if not journey or not journey.beneficiary_id:
        return
    commerce_order = journey.commerce_orders.order_by("-created_at").first()
    title, message = _journey_confirmation_copy(journey, commerce_order)
    template_key = "journey.confirmed"
    create_notification(
        recipient=journey.beneficiary,
        kind=NotificationKind.SYSTEM,
        category=_category_for(journey.activity),
        title=title,
        message=message,
        action_url=_journey_action(journey),
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
    subject = journey.activity.title
    order = journey.commerce_orders.order_by("-created_at").first()
    template_key = "journey.payment.required"
    create_notification(
        recipient=journey.beneficiary,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.PAYMENT,
        title="Paiement requis",
        message=f"Votre demande pour « {subject} » est approuvée. Vous pouvez maintenant effectuer le paiement.",
        action_url=_journey_action(journey),
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
    subject = request.journey.activity.title
    template_key = "journey.request.approved"
    create_notification(
        recipient=request.requester,
        kind=NotificationKind.SYSTEM,
        category=_category_for(request.journey.activity),
        title="Demande approuvée",
        message=f"Votre demande pour « {subject} » a été approuvée.",
        action_url=_journey_action(request.journey),
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

    workflow = access.journey.workflow if access.journey_id else None
    vocabulary = vocabulary_for(activity=access.activity, workflow=workflow)
    subject = access.activity.title
    if vocabulary.vertical == "transport":
        title = "Billet de voyage disponible"
        message = f"Votre billet de voyage pour « {subject} » est disponible."
    elif vocabulary.access_noun == "Billet":
        title = "Billet disponible"
        message = f"Votre billet pour « {subject} » est disponible."
    elif vocabulary.access_noun == "Invitation":
        title = "Invitation disponible"
        message = f"Votre invitation pour « {subject} » est disponible."
    elif vocabulary.access_noun == "Confirmation":
        title = "Inscription confirmée"
        message = f"Votre inscription à « {subject} » est confirmée."
    else:
        title = f"{vocabulary.access_noun} disponible"
        message = f"Votre {vocabulary.access_noun.lower()} pour « {subject} » est disponible."

    if access.journey_id and vocabulary.access_noun in {"Confirmation", "Invitation"}:
        dedup_key = f"journey-confirmed:{access.journey_id}:{access.beneficiary_id}"
    else:
        dedup_key = f"access-issued:{access.pk}:{access.beneficiary_id}"
    template_key = "access.issued"
    create_notification(
        recipient=access.beneficiary,
        kind=NotificationKind.TICKETS_ISSUED if vocabulary.access_noun == "Billet" else NotificationKind.SYSTEM,
        category=_category_for(access.activity),
        title=title,
        message=message,
        action_url=_access_action(access),
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
        activity = payment.order.event.activity
        journey = payment.order.journey
        return activity, journey, payment.commerce_order
    commerce_order = payment.commerce_order
    journey = commerce_order.journey if commerce_order else None
    activity = journey.activity if journey else None
    return activity, journey, commerce_order


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
    activity, journey, commerce_order = _payment_context(payment)
    subject = activity.title if activity else "votre démarche"
    if domain_event.event_type == DomainEventType.PAYMENT_SUCCEEDED:
        kind = NotificationKind.PAYMENT_SUCCEEDED
        title = "Paiement confirmé"
        message = f"Le paiement {payment.reference} de {payment.amount} {payment.currency} pour « {subject} » a été confirmé."
        template_key = "payment.succeeded"
    elif domain_event.event_type == DomainEventType.PAYMENT_FAILED:
        kind = NotificationKind.PAYMENT_FAILED
        title = "Paiement non confirmé"
        message = f"Le paiement pour « {subject} » n’a pas pu être confirmé."
        template_key = "payment.failed"
    else:
        kind = NotificationKind.PAYMENT_REFUNDED
        title = "Paiement remboursé"
        message = f"Le paiement {payment.reference} de {payment.amount} {payment.currency} a été remboursé."
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
    cancelled = domain_event.event_type == DomainEventType.OCCURRENCE_CANCELLED
    title, base_message = occurrence_change_copy(activity=occurrence.activity, cancelled=cancelled)
    if cancelled:
        message = base_message
        template_key = "occurrence.cancelled"
    else:
        starts = timezone.localtime(occurrence.start_at).strftime("%d/%m/%Y à %H:%M")
        message = f"{base_message} Nouvelle date : {starts}."
        template_key = "occurrence.rescheduled"
    for recipient in occurrence_recipients(occurrence):
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=_category_for(occurrence.activity),
            title=title,
            message=message,
            action_url="",
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
