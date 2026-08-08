from django.db.models import Q
from django.utils import timezone

from accounts.api.permissions import user_has_role
from events.models import Event, EventStatus
from organizations.permissions import ACCESS_ROLES

from .models import ScanLog, ScannerAssignment


def _organization_access_filter(prefix: str, user) -> Q:
    return Q(
        **{
            f"{prefix}organization__memberships__user": user,
            f"{prefix}organization__memberships__is_active": True,
            f"{prefix}organization__memberships__role__in": ACCESS_ROLES,
        }
    )


def get_scannable_events(user):
    queryset = Event.objects.select_related("organizer", "organization", "venue").filter(
        status=EventStatus.PUBLISHED,
        end_at__gt=timezone.now(),
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset

    access_filter = Q(organizer=user) | _organization_access_filter("", user)

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

    return queryset.filter(access_filter | assignment_filter).distinct()


def get_scan_logs_visible_to(user):
    queryset = ScanLog.objects.select_related(
        "event",
        "event__organization",
        "ticket",
        "ticket__ticket_type",
        "scanner",
        "assignment",
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset

    return queryset.filter(
        Q(event__organizer=user)
        | _organization_access_filter("event__", user)
        | Q(scanner=user)
    ).distinct()


def get_assignments_visible_to(user):
    queryset = ScannerAssignment.objects.select_related(
        "event",
        "event__organization",
        "agent",
        "assigned_by",
    )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset

    return queryset.filter(
        Q(event__organizer=user)
        | _organization_access_filter("event__", user)
        | Q(agent=user)
    ).distinct()
