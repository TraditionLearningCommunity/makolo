from rest_framework.permissions import BasePermission

from events.permissions import user_can_manage_event_access

from .models import ScannerAssignment


def get_active_assignment(user, event):
    if not getattr(user, "is_authenticated", False):
        return None
    assignments = ScannerAssignment.objects.select_related("access_gate").filter(
        event=event,
        agent=user,
        is_active=True,
    )
    for assignment in assignments:
        if assignment.is_current:
            return assignment
    return None


def user_can_scan_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_can_manage_event_access(user, event):
        return True
    # Assignment is already an explicit event-scoped authority. The historical
    # global User.is_scanner_agent/Role flag is no longer required.
    return get_active_assignment(user, event) is not None


def user_can_manage_scanner_assignments(user, event) -> bool:
    return user_can_manage_event_access(user, event)


class CanUseScanner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanManageScannerAssignments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return user_can_manage_scanner_assignments(request.user, obj.event)
