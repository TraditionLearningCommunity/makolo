from rest_framework.permissions import BasePermission

from authorization.constants import PermissionCode
from authorization.services import can, effective_permission_codes


def _has_legacy_organizer_role(user) -> bool:
    roles = getattr(user, "roles", None)
    return bool(
        roles is not None
        and roles.filter(code="organizer", is_active=True).exists()
    )


def user_can_manage_events(user) -> bool:
    """Return whether the profile may enter an Event creation surface.

    Canonical mandates are authoritative. Historical organizer markers remain
    narrow compatibility entry points while existing profiles are migrated;
    object-level operations still require authority on the Activity or
    authorship of that Activity.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False):
        return True
    effective = effective_permission_codes(user)
    if (
        PermissionCode.SPACE_ACTIVITIES_MANAGE in effective
        or PermissionCode.ACTIVITY_MANAGE in effective
    ):
        return True
    return bool(
        getattr(user, "is_organizer", False)
        or _has_legacy_organizer_role(user)
    )


def _legacy_personal_creator(user, event) -> bool:
    """Preserve the original Event creator's authority after the cutover.

    Before Event became an Activity vertical, ``Event.organizer`` carried this
    responsibility even when an organization was attached. The canonical
    equivalent is ``Activity.created_by``; no generic value is copied back to
    Event.
    """
    return bool(
        getattr(user, "is_authenticated", False)
        and event.activity.created_by_id == user.pk
    )


def user_can_manage_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or _legacy_personal_creator(user, event):
        return True
    return can(user, PermissionCode.ACTIVITY_MANAGE, activity=event.activity)


def user_can_manage_event_finance(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or _legacy_personal_creator(user, event):
        return True
    space = event.activity.space
    return bool(space is not None and can(user, PermissionCode.FINANCE_MANAGE, space))


def user_can_manage_event_access(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or _legacy_personal_creator(user, event):
        return True
    space = event.activity.space
    return bool(space is not None and can(user, PermissionCode.ACCESS_MANAGE, space))


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_event(request.user, obj)
