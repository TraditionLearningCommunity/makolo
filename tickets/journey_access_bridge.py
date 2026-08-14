from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from access.legacy_bridge import sync_legacy_access_status, transfer_access_beneficiary
from access.models import AccessStatus
from access.services import issue_access
from events.activity_bridge import sync_event_core
from journeys.legacy_bridge import sync_legacy_journey_status
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey

from .models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus


ORDER_STATUS_MAP = {
    TicketOrderStatus.PENDING: JourneyStatus.PENDING_PAYMENT,
    TicketOrderStatus.CANCELLED: JourneyStatus.CANCELLED,
    TicketOrderStatus.EXPIRED: JourneyStatus.EXPIRED,
}

TICKET_STATUS_MAP = {
    TicketStatus.VALID: AccessStatus.VALID,
    TicketStatus.USED: AccessStatus.USED,
    TicketStatus.CANCELLED: AccessStatus.CANCELLED,
    TicketStatus.REFUNDED: AccessStatus.REVOKED,
}


def _profile_from_email(email):
    email = (email or "").strip()
    if not email:
        return None
    return get_user_model().objects.filter(email__iexact=email, is_active=True).first()


def _order_beneficiary(order):
    return order.buyer or _profile_from_email(order.customer_email)


def _ticket_beneficiary(ticket):
    return ticket.owner or _profile_from_email(ticket.holder_email) or _order_beneficiary(ticket.order)


def _order_journey_status(order):
    if order.status == TicketOrderStatus.CONFIRMED:
        return JourneyStatus.FULFILLED if order.tickets.exists() else JourneyStatus.CONFIRMED
    return ORDER_STATUS_MAP[order.status]


@transaction.atomic
def sync_order_journey(order: TicketOrder):
    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related("event__activity", "buyer", "journey")
        .order_by()
        .get(pk=order.pk)
    )
    beneficiary = _order_beneficiary(order)
    if beneficiary is None:
        return None

    activity, occurrence = sync_event_core(order.event)
    target_status = _order_journey_status(order)
    if order.journey_id:
        journey = order.journey
        if (
            journey.activity_id != activity.pk
            or journey.occurrence_id != occurrence.pk
            or journey.beneficiary_id != beneficiary.pk
        ):
            raise ValueError("Le bridge TicketOrder pointe vers une Démarche incohérente.")
        return sync_legacy_journey_status(
            journey=journey,
            status=target_status,
            actor=None,
            reason="ticket_order_bridge",
        )

    journey = create_journey(
        initiated_by=beneficiary,
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        workflow=WorkflowKind.PURCHASE,
        status=target_status,
        expires_at=order.expires_at,
    )
    TicketOrder.objects.filter(pk=order.pk).update(journey=journey)
    order.journey = journey
    return journey


@transaction.atomic
def sync_ticket_access(ticket: Ticket):
    ticket = (
        Ticket.objects.select_for_update(of=("self",))
        .select_related(
            "event__activity",
            "ticket_type",
            "order__journey",
            "owner",
            "access__beneficiary",
            "access__activity",
            "access__occurrence",
            "access__journey",
        )
        .order_by()
        .get(pk=ticket.pk)
    )
    beneficiary = _ticket_beneficiary(ticket)
    if beneficiary is None:
        # Controlled legacy compatibility for beta guest tickets whose holder
        # cannot be deterministically linked to a Makolo Profile.
        return None

    journey = ticket.order.journey or sync_order_journey(ticket.order)
    activity, occurrence = sync_event_core(ticket.event)
    target_status = TICKET_STATUS_MAP[ticket.status]

    if ticket.access_id:
        access = ticket.access
        if access.activity_id != activity.pk or access.occurrence_id != occurrence.pk:
            raise ValueError("Le bridge Ticket pointe vers un Accès incohérent.")
        if journey is not None and access.journey_id not in {None, journey.pk}:
            raise ValueError("L’Accès du Ticket provient d’une autre Démarche.")
        if access.beneficiary_id != beneficiary.pk:
            access = transfer_access_beneficiary(
                access=access,
                beneficiary=beneficiary,
                actor=None,
                source="ticket_transfer",
            )
        access = sync_legacy_access_status(
            access=access,
            status=target_status,
            source="ticket_bridge",
        )
        return access

    access = issue_access(
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        journey=journey,
        status=target_status,
        valid_from=None,
        valid_until=ticket.event.end_at,
        single_use=True,
        source_key=f"ticket:{ticket.pk}",
        create_credential=True,
    )
    Ticket.objects.filter(pk=ticket.pk).update(access=access)
    ticket.access = access
    return access


def sync_ticket_access_ids(ticket_ids):
    for ticket_id in ticket_ids:
        ticket = Ticket.objects.filter(pk=ticket_id).first()
        if ticket is not None:
            sync_ticket_access(ticket)


@receiver(post_save, sender=TicketOrder, dispatch_uid="tickets.sync_order_journey")
def _ticket_order_saved(sender, instance, **kwargs):
    sync_order_journey(instance)


@receiver(post_save, sender=Ticket, dispatch_uid="tickets.sync_ticket_access")
def _ticket_saved(sender, instance, **kwargs):
    sync_ticket_access(instance)
