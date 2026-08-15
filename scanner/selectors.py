from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from events.models import Event, EventStatus

from .models import EventAccessGate, ScanLog, ScannerAssignment


def _space_filter(prefix: str, space_ids) -> Q:
    if not space_ids:
        return Q(pk__isnull=True)
    return Q(**{f"{prefix}organization_id__in": space_ids})


def _active_assignment_filter(user) -> Q:
    now = timezone.now()
    return Q(scanner_assignments__agent=user, scanner_assignments__is_active=True) & (
        Q(scanner_assignments__valid_from__isnull=True)
        | Q(scanner_assignments__valid_from__lte=now)
    ) & (
        Q(scanner_assignments__valid_until__isnull=True)
        | Q(scanner_assignments__valid_until__gt=now)
    )


def get_scannable_events(user):
    queryset = Event.objects.select_related("organizer", "organization", "venue", "activity").filter(
        status=EventStatus.PUBLISHED,
        end_at__gt=timezone.now(),
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ACCESS_MANAGE)
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_ACCESS_SCAN)
    if space_ids is None or activity_ids is None:
        return queryset
    contextual = _space_filter("", space_ids)
    return queryset.filter(
        contextual
        | Q(activity_id__in=activity_ids)
        | Q(organization__isnull=True, organizer=user)
        | _active_assignment_filter(user)
    ).distinct()


def get_scan_logs_visible_to(user):
    queryset = ScanLog.objects.select_related(
        "event",
        "event__organization",
        "event__activity",
        "ticket",
        "ticket__ticket_type",
        "scanner",
        "assignment",
        "assignment__activity",
        "assignment__occurrence",
        "access_gate",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ACCESS_MANAGE)
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_ACCESS_MANAGE)
    if space_ids is None or activity_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    return queryset.filter(
        contextual
        | Q(event__activity_id__in=activity_ids)
        | Q(event__organization__isnull=True, event__organizer=user)
        | Q(scanner=user)
    ).distinct()


def get_assignments_visible_to(user):
    queryset = ScannerAssignment.objects.select_related(
        "activity",
        "activity__space",
        "occurrence",
        "event",
        "event__organization",
        "agent",
        "assigned_by",
        "access_gate",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ACCESS_MANAGE)
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_ACCESS_MANAGE)
    if space_ids is None or activity_ids is None:
        return queryset
    return queryset.filter(
        Q(activity__space_id__in=space_ids)
        | Q(activity_id__in=activity_ids)
        | Q(event__organization__isnull=True, event__organizer=user)
        | Q(agent=user)
    ).distinct()


def get_current_assignments_visible_to(user):
    now = timezone.now()
    return get_assignments_visible_to(user).filter(is_active=True).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_until__isnull=True) | Q(valid_until__gt=now),
    )


def get_access_gates_visible_to(user):
    queryset = EventAccessGate.objects.select_related(
        "event", "event__organization", "event__activity", "created_by"
    ).prefetch_related("assignments")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ACCESS_MANAGE)
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_ACCESS_MANAGE)
    if space_ids is None or activity_ids is None:
        return queryset
    contextual = _space_filter("event__", space_ids)
    return queryset.filter(
        contextual
        | Q(event__activity_id__in=activity_ids)
        | Q(event__organization__isnull=True, event__organizer=user)
        | Q(assignments__agent=user, assignments__is_active=True)
    ).distinct()
