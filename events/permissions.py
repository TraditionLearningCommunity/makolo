from rest_framework.permissions import BasePermission

from authorization.constants import PermissionCode
from authorization.services import can


def user_can_manage_events(user) -> bool:
    """Any authenticated Profile may create a personal Event.

    The selected operator is revalidated by the creation service. Global
    organizer flags are no longer an authority gate for entering this surface.
    """
    return bool(getattr(user, "is_authenticated", False))


def _legacy_unresolved_creator(user, event) -> bool:
    """Narrow compatibility for pre-T24 Activities with unresolved ownership."""
    activity = event.activity
    return bool(
        getattr(user, "is_authenticated", False)
        and activity.space_id is None
        and getattr(activity, "owner_profile_id", None) is None
        and activity.created_by_id == user.pk
    )


def user_can_manage_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if _legacy_unresolved_creator(user, event):
        return True
    return can(user, PermissionCode.ACTIVITY_MANAGE, activity=event.activity)


def user_can_manage_event_finance(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    space = event.activity.space
    return bool(space is not None and can(user, PermissionCode.FINANCE_MANAGE, space))


def user_can_manage_event_access(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    space = event.activity.space
    if space is not None:
        return can(user, PermissionCode.ACCESS_MANAGE, space)
    return can(user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=event.activity)


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_event(request.user, obj)
