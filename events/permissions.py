from rest_framework.permissions import BasePermission

from accounts.api.permissions import user_has_role
from authorization.constants import PermissionCode
from authorization.services import can, effective_permission_codes


def user_can_manage_events(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    effective = effective_permission_codes(user)
    if PermissionCode.SPACE_ACTIVITIES_MANAGE in effective or PermissionCode.ACTIVITY_MANAGE in effective:
        return True
    return user_has_role(user, "organizer", legacy_flag="is_organizer")


def _is_legacy_event_organizer(user, event) -> bool:
    return bool(
        not event.organization_id
        and event.organizer_id == user.pk
        and user_has_role(user, "organizer", legacy_flag="is_organizer")
    )


def user_can_manage_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if event.activity_id:
        if can(user, PermissionCode.ACTIVITY_MANAGE, activity=event.activity):
            return True
        # Event -> Activity is an expand/backfill bridge. Creating the canonical
        # Activity must not silently remove the historical organizer authority
        # of a standalone Event before Event itself is cut over.
        return _is_legacy_event_organizer(user, event)
    if event.organization_id:
        return can(user, PermissionCode.SPACE_ACTIVITIES_MANAGE, event.organization)
    return _is_legacy_event_organizer(user, event)


def user_can_manage_event_finance(user, event) -> bool:
    if not getattr(user, "is_authenticated", False): return False
    if event.organization_id: return can(user, PermissionCode.FINANCE_MANAGE, event.organization)
    return user_can_manage_event(user, event)


def user_can_manage_event_access(user, event) -> bool:
    if not getattr(user, "is_authenticated", False): return False
    if event.organization_id: return can(user, PermissionCode.ACCESS_MANAGE, event.organization)
    return user_can_manage_event(user, event)


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view): return user_can_manage_events(request.user)

class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view): return request.user.is_authenticated
    def has_object_permission(self, request, view, obj): return user_can_manage_event(request.user, obj)