from django.db.models import Q

from events.models import EventStatus, EventVisibility
from organizations.permissions import ACCESS_ROLES, EVENT_MANAGEMENT_ROLES, FINANCE_ROLES

from .models import Ticket, TicketOrder, TicketTransfer, TicketType, TicketWaitlistEntry


def _organization_role_filter(prefix: str, user, roles) -> Q:
    return Q(
        **{
            f"{prefix}organization__memberships__user": user,
            f"{prefix}organization__memberships__is_active": True,
            f"{prefix}organization__memberships__role__in": roles,
        }
    )


def get_public_ticket_types_for_event(event):
    """Participant-facing ticket inventory for one already-public event.

    Inactive ticket types are treated as internal/unavailable and are never
    exposed through the mobile checkout contract.
    """
    return (
        TicketType.objects.select_related("event")
        .filter(event=event, is_active=True)
        .order_by("price", "name")
    )


def get_ticket_types_visible_to(user):
    queryset = TicketType.objects.select_related("event", "event__organizer", "event__organization")
    public_filter = Q(
        is_active=True,
        event__status=EventStatus.PUBLISHED,
        event__visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    )

    if user.is_authenticated and user.is_staff:
        return queryset
    if user.is_authenticated:
        managed_filter = Q(event__organizer=user) | _organization_role_filter(
            "event__", user, EVENT_MANAGEMENT_ROLES
        )
        return queryset.filter(public_filter | managed_filter).distinct()
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

    # Orders contain customer identity, totals and lifecycle information. They
    # are visible only to the buyer and organization roles that actually need
    # billetterie/finance access — not to every organization member.
    organization_roles = set(EVENT_MANAGEMENT_ROLES) | set(FINANCE_ROLES)
    return queryset.filter(
        Q(buyer=user)
        | Q(event__organizer=user)
        | _organization_role_filter("event__", user, organization_roles)
    ).distinct()


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

    # Ticket holder data is operational. Event managers and access managers
    # may inspect it; marketing-only members must not inherit that visibility.
    organization_roles = set(EVENT_MANAGEMENT_ROLES) | set(ACCESS_ROLES)
    return queryset.filter(
        Q(owner=user)
        | Q(event__organizer=user)
        | _organization_role_filter("event__", user, organization_roles)
    ).distinct()


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
