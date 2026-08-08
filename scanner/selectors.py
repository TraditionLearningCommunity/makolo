from django.db.models import Q
from django.utils import timezone

from accounts.api.permissions import user_has_role
from events.models import Event, EventStatus
from events.permissions import user_can_manage_events

from .models import ScanLog, ScannerAssignment


def get_scannable_events(user):
    queryset = Event.objects.select_related("organizer", "venue").filter(
        status=EventStatus.PUBLISHED,
        end_at__gt=timezone.now(),
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if user.is_staff:
        return queryset

    if user_can_manage_events(user):
        owner_filter = Q(organizer=user)
    else:
        owner_filter = Q(pk__isnull=True)

    if user_has_role(user, "scanner-agent", legacy_flag="is_scanner_agent"):
        assignment_filter = Q(
            scanner_assignments__agent=user,
            scanner_assignments__is_active=True,
        ) & (
            Q(scanner_assignments__valid_from__isnull=True)
            | Q(scanner_assignments__valid_from__lte=timezone.now())
        ) & (
            Q(scanner_assignments__valid_until__isnull=True)
            | Q(scanner_assignments__valid_until__gte=timezone.now())
        )
    else:
        assignment_filter = Q(pk__isnull=True)

    return queryset.filter(owner_filter | assignment_filter).distinct()


def get_scan_logs_visible_to(user):
    queryset = ScanLog.objects.select_related(
        "event",
        "ticket",
        "ticket__ticket_type",
        "scanner",
        "assignment",
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if user.is_staff:
        return queryset

    if user_can_manage_events(user):
        organizer_filter = Q(event__organizer=user)
    else:
        organizer_filter = Q(pk__isnull=True)

    return queryset.filter(organizer_filter | Q(scanner=user)).distinct()


def get_assignments_visible_to(user):
    queryset = ScannerAssignment.objects.select_related(
        "event",
        "agent",
        "assigned_by",
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if user.is_staff:
        return queryset

    if user_can_manage_events(user):
        return queryset.filter(Q(event__organizer=user) | Q(agent=user)).distinct()

    return queryset.filter(agent=user)
