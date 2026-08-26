from rest_framework.permissions import BasePermission

from authorization.constants import PermissionCode
from authorization.services import can
from events.permissions import user_can_manage_event_finance
from tickets.permissions import user_can_access_order


def _commerce_payment_context(payment):
    if not payment.commerce_order_id:
        return None, None
    order = payment.commerce_order
    activity = order.journey.activity
    space = order.payee_space or activity.space
    return space, activity


def user_can_access_payment(user, payment) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if payment.order_id:
        return user_can_access_order(user, payment.order)
    if not payment.commerce_order_id:
        return False
    if getattr(user, "is_staff", False):
        return True
    order = payment.commerce_order
    if order.buyer_id == user.pk or payment.initiated_by_id == user.pk:
        return True
    space, activity = _commerce_payment_context(payment)
    if space is not None and can(user, PermissionCode.FINANCE_VIEW, space):
        return True
    return bool(activity is not None and can(user, PermissionCode.ACTIVITY_FINANCE_VIEW, activity=activity))


def user_can_manage_payment(user, payment) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if payment.order_id:
        return user_can_manage_event_finance(user, payment.order.event)
    if not payment.commerce_order_id:
        return False
    if getattr(user, "is_staff", False):
        return True
    space, activity = _commerce_payment_context(payment)
    if space is not None and can(user, PermissionCode.FINANCE_MANAGE, space):
        return True
    return bool(activity is not None and can(user, PermissionCode.ACTIVITY_FINANCE_MANAGE, activity=activity))


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
