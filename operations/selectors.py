from django.db.models import Count

from events.models import Event
from organizations.models import Organization

from .models import ModerationCase, OperationsAuditLog, OperationsIncident, WorkerHeartbeat
from .permissions import user_can_access_operations


def _staff_queryset(user, queryset):
    if not user_can_access_operations(user):
        return queryset.none()
    return queryset


def get_operations_incidents(user):
    queryset = OperationsIncident.objects.select_related(
        "organization", "event", "payment", "scan_log", "opened_by", "assigned_to"
    )
    return _staff_queryset(user, queryset)


def get_moderation_cases(user):
    queryset = ModerationCase.objects.select_related(
        "organization", "event", "opened_by", "assigned_to"
    )
    return _staff_queryset(user, queryset)


def get_operations_audit_logs(user):
    queryset = OperationsAuditLog.objects.select_related("actor")
    return _staff_queryset(user, queryset)


def get_worker_heartbeats(user):
    return _staff_queryset(user, WorkerHeartbeat.objects.all())


def get_operations_organizations(user):
    queryset = Organization.objects.annotate(
        event_count=Count("events", distinct=True),
        member_count=Count("memberships", distinct=True),
    ).order_by("verification_status", "-created_at")
    return _staff_queryset(user, queryset)


def get_operations_events(user):
    queryset = Event.objects.select_related("organization", "organizer", "category", "venue").order_by(
        "-created_at"
    )
    return _staff_queryset(user, queryset)
