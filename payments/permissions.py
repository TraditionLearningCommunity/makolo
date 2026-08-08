from rest_framework.permissions import BasePermission

from events.permissions import user_can_manage_event_finance
from tickets.permissions import user_can_access_order


def user_can_access_payment(user, payment) -> bool:
    return user_can_access_order(user, payment.order)


def user_can_manage_payment(user, payment) -> bool:
    return user_can_manage_event_finance(user, payment.order.event)


class CanAccessPayment(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_access_payment(request.user, obj)


class CanManagePayment(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_payment(request.user, obj)
