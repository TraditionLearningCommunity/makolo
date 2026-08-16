from rest_framework.permissions import BasePermission

from authorization.constants import PermissionCode
from authorization.services import can, effective_permission_codes


def user_can_manage_events(user) -> bool:
    """Creation/navigation capability, derived only from canonical permissions."""
    if not getattr(user, "is_authenticated", False):
        return False
    effective = effective_permission_codes(user)
    return bool(
        PermissionCode.SPACE_ACTIVITIES_MANAGE in effective
        or PermissionCode.ACTIVITY_MANAGE in effective
    )


def _legacy_personal_creator(user, event) -> bool:
    """Compatibility for pre-Space personal Events only."""
    return bool(
        event.activity.space_id is None
        and event.activity.created_by_id == user.pk
    )


def user_can_manage_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if can(user, PermissionCode.ACTIVITY_MANAGE, activity=event.activity):
        return True
    return _legacy_personal_creator(user, event)


def user_can_manage_event_finance(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    space = event.activity.space
    if space is not None:
        return can(user, PermissionCode.FINANCE_MANAGE, space)
    return _legacy_personal_creator(user, event)


def user_can_manage_event_access(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    space = event.activity.space
    if space is not None:
        return can(user, PermissionCode.ACCESS_MANAGE, space)
    return _legacy_personal_creator(user, event)


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_event(request.user, obj)
