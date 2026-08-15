from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from authorization.constants import PermissionCode
from authorization.services import can
from events.permissions import user_can_manage_event_access

from .models import ScannerAssignment


def _event_occurrence(event):
    activity = getattr(event, "activity", None)
    if activity is None:
        return None
    return (
        activity.occurrences.filter(start_at=event.start_at, end_at=event.end_at)
        .order_by("id")
        .first()
    )


def get_active_assignment(user, event=None, *, activity=None, occurrence=None):
    if not getattr(user, "is_authenticated", False):
        return None
    if activity is None and event is not None:
        activity = getattr(event, "activity", None)
        if occurrence is None:
            occurrence = _event_occurrence(event)

    now = timezone.now()
    assignments = ScannerAssignment.objects.select_related(
        "activity", "occurrence", "event", "access_gate"
    ).filter(agent=user, is_active=True).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_until__isnull=True) | Q(valid_until__gt=now),
    )
    if activity is not None:
        scoped = assignments.filter(activity=activity)
        if occurrence is None:
            match = scoped.filter(occurrence__isnull=True).order_by("created_at").first()
        else:
            eligible = scoped.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
            match = eligible.filter(occurrence=occurrence).order_by("created_at").first()
            match = match or eligible.filter(occurrence__isnull=True).order_by("created_at").first()
        if match is not None:
            return match
        # Expand/backfill compatibility: an old Event-scoped assignment may
        # legitimately survive without a deterministic canonical occurrence.
        # It remains a delegation bridge, while Access still makes the final
        # Activity/Occurrence decision.
        if event is not None:
            return assignments.filter(event=event).order_by("created_at").first()
        return None

    if event is not None:
        return assignments.filter(event=event).order_by("created_at").first()
    return None


def user_can_scan_activity(user, activity, *, occurrence=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if can(user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=activity):
        return True
    if activity.space_id and can(user, PermissionCode.ACCESS_MANAGE, activity.space):
        return True
    return get_active_assignment(user, activity=activity, occurrence=occurrence) is not None


def user_can_scan_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    # Events keeps its historical organizer/access-manager authority while the
    # scanner engine itself moves to Activity/Occurrence. This is a bridge, not
    # a new source of Access validity.
    if user_can_manage_event_access(user, event):
        return True
    activity = getattr(event, "activity", None)
    if activity is not None:
        if can(user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=activity):
            return True
        if activity.space_id and can(user, PermissionCode.ACCESS_MANAGE, activity.space):
            return True
        return get_active_assignment(
            user,
            event,
            activity=activity,
            occurrence=_event_occurrence(event),
        ) is not None
    return get_active_assignment(user, event) is not None


def user_can_manage_activity_scanner_assignments(user, activity) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if can(user, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=activity):
        return True
    return bool(activity.space_id and can(user, PermissionCode.ACCESS_MANAGE, activity.space))


def user_can_manage_scanner_assignments(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_can_manage_event_access(user, event):
        return True
    activity = getattr(event, "activity", None)
    if activity is not None:
        return user_can_manage_activity_scanner_assignments(user, activity)
    return False


class CanUseScanner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanManageScannerAssignments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.activity_id and user_can_manage_activity_scanner_assignments(request.user, obj.activity):
            return True
        if obj.event_id:
            return user_can_manage_scanner_assignments(request.user, obj.event)
        return False
