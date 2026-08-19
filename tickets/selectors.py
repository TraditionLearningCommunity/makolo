from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from commerce.models import OfferStatus
from events.models import EventStatus, EventVisibility

from .models import Ticket, TicketOrder, TicketTransfer, TicketType, TicketWaitlistEntry


def _space_filter(prefix: str, space_ids) -> Q:
    if not space_ids:
        return Q(pk__isnull=True)
    return Q(**{f"{prefix}activity__space_id__in": space_ids})


def get_public_ticket_types_for_event(event):
    return (
        TicketType.objects.select_related("event__activity", "offer", "capacity_pool")
        .filter(
            event=event,
            offer__status=OfferStatus.ACTIVE,
            capacity_pool__is_active=True,
            is_public=True,
        )
        .order_by("offer__unit_price", "name")
    )


def get_ticket_types_visible_to(user):
    queryset = TicketType.objects.select_related(
        "event__activity",
        "event__activity__created_by",
        "event__activity__space",
        "offer",
        "capacity_pool",
    )
    public_filter = Q(
        offer__status=OfferStatus.ACTIVE,
        capacity_pool__is_active=True,
        is_public=True,
        event__activity__status=EventStatus.PUBLISHED,
        event__activity__visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.filter(public_filter)

    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_MANAGE)
    if activity_ids is None:
        return queryset
    managed_filter = Q(event__activity_id__in=activity_ids) if activity_ids else Q(pk__isnull=True)
    legacy_personal = Q(event__activity__space__isnull=True, event__activity__created_by=user)
    return queryset.filter(public_filter | managed_filter | legacy_personal).distinct()


def get_orders_visible_to(user):
    queryset = TicketOrder.objects.select_related(
        "event__activity",
        "event__activity__created_by",
        "event__activity__space",
        "buyer",
        "journey",
        "commerce_order",
    ).prefetch_related("items__ticket_type__offer", "tickets__ticket_type", "tickets__access")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.ORDERS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    legacy_personal = Q(event__activity__space__isnull=True, event__activity__created_by=user)
    return queryset.filter(Q(buyer=user) | contextual | legacy_personal).distinct()


def get_tickets_visible_to(user):
    queryset = Ticket.objects.select_related(
        "event__activity",
        "event__activity__created_by",
        "event__activity__space",
        "ticket_type__offer",
        "ticket_type__capacity_pool",
        "order__commerce_order",
        "owner",
        "access",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.TICKETS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    legacy_personal = Q(event__activity__space__isnull=True, event__activity__created_by=user)
    return queryset.filter(Q(owner=user) | contextual | legacy_personal).distinct()


def get_waitlist_entries_visible_to(user):
    queryset = TicketWaitlistEntry.objects.select_related(
        "ticket_type__event__activity",
        "ticket_type__offer",
        "ticket_type__capacity_pool",
        "user",
        "offered_order__commerce_order",
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
        "ticket__event__activity",
        "ticket__ticket_type__offer",
        "ticket__access",
        "sender",
        "recipient",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.TICKETS_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("ticket__event__", space_ids)
    return queryset.filter(Q(sender=user) | Q(recipient=user) | contextual).distinct()
