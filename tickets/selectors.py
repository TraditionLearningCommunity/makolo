from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from events.models import EventStatus, EventVisibility

from .models import Ticket, TicketOrder, TicketTransfer, TicketType, TicketWaitlistEntry


def _space_filter(prefix: str, space_ids) -> Q:
    if not space_ids:
        return Q(pk__isnull=True)
    return Q(**{f"{prefix}organization_id__in": space_ids})


def get_public_ticket_types_for_event(event):
    return (
        TicketType.objects.select_related("event")
        .filter(event=event, is_active=True, is_public=True)
        .order_by("price", "name")
    )


def get_ticket_types_visible_to(user):
    queryset = TicketType.objects.select_related("event", "event__organizer", "event__organization")
    public_filter = Q(
        is_active=True,
        is_public=True,
        event__status=EventStatus.PUBLISHED,
        event__visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.filter(public_filter)

    space_ids = space_ids_with_permission(user, PermissionCode.ACTIVITY_MANAGE)
    if space_ids is None:
        return queryset
    managed_filter = _space_filter("event__", space_ids) | Q(
        event__organization__isnull=True,
        event__organizer=user,
    )
    return queryset.filter(public_filter | managed_filter).distinct()


def get_orders_visible_to(user):
    queryset = TicketOrder.objects.select_related(
        "event", "event__organizer", "event__organization", "buyer"
    ).prefetch_related("items__ticket_type", "tickets__ticket_type")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ORDERS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    return queryset.filter(
        Q(buyer=user)
        | contextual
        | Q(event__organization__isnull=True, event__organizer=user)
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
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.TICKETS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    return queryset.filter(
        Q(owner=user)
        | contextual
        | Q(event__organization__isnull=True, event__organizer=user)
    ).distinct()


def get_waitlist_entries_visible_to(user):
    queryset = TicketWaitlistEntry.objects.select_related(
        "ticket_type__event", "user", "offered_order"
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.ORDERS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("ticket_type__event__", space_ids)
    return queryset.filter(Q(user=user) | contextual).distinct()


def get_ticket_transfers_visible_to(user):
    queryset = TicketTransfer.objects.select_related(
        "ticket__event", "ticket__ticket_type", "sender", "recipient"
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.TICKETS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("ticket__event__", space_ids)
    return queryset.filter(Q(sender=user) | Q(recipient=user) | contextual).distinct()
