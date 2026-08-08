from rest_framework.permissions import BasePermission

from events.permissions import (
    user_can_manage_event,
    user_can_manage_event_finance,
    user_can_manage_events,
)


def user_can_manage_ticket_type(user, ticket_type) -> bool:
    return user_can_manage_event(user, ticket_type.event)


def user_can_access_order(user, order) -> bool:
    if not user.is_authenticated:
        return False
    if user_can_manage_event(user, order.event) or user_can_manage_event_finance(user, order.event):
        return True
    return order.buyer_id == user.pk


def user_can_access_ticket(user, ticket) -> bool:
    if not user.is_authenticated:
        return False
    if user_can_manage_event(user, ticket.event):
        return True
    return ticket.owner_id == user.pk


def user_can_access_waitlist_entry(user, entry) -> bool:
    return bool(getattr(user, "is_authenticated", False) and (user.is_staff or entry.user_id == user.pk))


def user_can_access_transfer(user, transfer) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (user.is_staff or transfer.sender_id == user.pk or transfer.recipient_id == user.pk)
    )


class IsTicketOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsTicketTypeOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_ticket_type(request.user, obj)


class IsOrderParticipantOrOrganizer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_access_order(request.user, obj)
