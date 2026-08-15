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
        assignments = assignments.filter(activity=activity)
        if occurrence is None:
            assignments = assignments.filter(occurrence__isnull=True)
        else:
            assignments = assignments.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence)).order_by(
                "occurrence_id", "created_at"
            )
            exact = assignments.filter(occurrence=occurrence).first()
            return exact or assignments.filter(occurrence__isnull=True).first()
        return assignments.order_by("created_at").first()

    # Transitional compatibility for historical rows whose Event could not be
    # deterministically mapped during the expand/backfill migration.
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
    activity = getattr(event, "activity", None)
    if activity is not None:
        return user_can_scan_activity(user, activity, occurrence=_event_occurrence(event))
    if user_can_manage_event_access(user, event):
        return True
    return get_active_assignment(user, event) is not None


def user_can_manage_activity_scanner_assignments(user, activity) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if can(user, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=activity):
        return True
    return bool(activity.space_id and can(user, PermissionCode.ACCESS_MANAGE, activity.space))


def user_can_manage_scanner_assignments(user, event) -> bool:
    activity = getattr(event, "activity", None)
    if activity is not None:
        return user_can_manage_activity_scanner_assignments(user, activity)
    return user_can_manage_event_access(user, event)


class CanUseScanner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanManageScannerAssignments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.activity_id:
            return user_can_manage_activity_scanner_assignments(request.user, obj.activity)
        if obj.event_id:
            return user_can_manage_scanner_assignments(request.user, obj.event)
        return False
