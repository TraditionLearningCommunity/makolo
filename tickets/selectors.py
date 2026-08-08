from django.db.models import Q

from events.models import EventStatus, EventVisibility
from events.permissions import user_can_manage_events

from .models import Ticket, TicketOrder, TicketTransfer, TicketType, TicketWaitlistEntry


def get_ticket_types_visible_to(user):
    queryset = TicketType.objects.select_related("event", "event__organizer", "event__organization")
    public_filter = Q(
        is_active=True,
        event__status=EventStatus.PUBLISHED,
        event__visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    )

    if user.is_authenticated and user.is_staff:
        return queryset
    if user.is_authenticated and user_can_manage_events(user):
        return queryset.filter(
            public_filter
            | Q(event__organizer=user)
            | Q(event__organization__memberships__user=user, event__organization__memberships__is_active=True)
        ).distinct()
    return queryset.filter(public_filter)


def get_orders_visible_to(user):
    queryset = TicketOrder.objects.select_related(
        "event",
        "event__organizer",
        "event__organization",
        "buyer",
    ).prefetch_related(
        "items__ticket_type",
        "tickets__ticket_type",
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset
    if user_can_manage_events(user):
        return queryset.filter(
            Q(buyer=user)
            | Q(event__organizer=user)
            | Q(event__organization__memberships__user=user, event__organization__memberships__is_active=True)
        ).distinct()
    return queryset.filter(buyer=user)


def get_tickets_visible_to(user):
    queryset = Ticket.objects.select_related(
        "event",
        "event__organizer",
        "event__organization",
        "ticket_type",
        "order",
        "owner",
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset
    if user_can_manage_events(user):
        return queryset.filter(
            Q(owner=user)
            | Q(event__organizer=user)
            | Q(event__organization__memberships__user=user, event__organization__memberships__is_active=True)
        ).distinct()
    return queryset.filter(owner=user)


def get_waitlist_entries_visible_to(user):
    queryset = TicketWaitlistEntry.objects.select_related(
        "ticket_type__event",
        "user",
        "offered_order",
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset
    return queryset.filter(user=user)


def get_ticket_transfers_visible_to(user):
    queryset = TicketTransfer.objects.select_related(
        "ticket__event",
        "ticket__ticket_type",
        "sender",
        "recipient",
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset
    return queryset.filter(Q(sender=user) | Q(recipient=user)).distinct()
