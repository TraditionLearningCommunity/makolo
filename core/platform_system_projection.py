"""Safe, read-only System projections; Domain Events own facts and delivery.

No payload, traceback, idempotency key or secrets are projected. Retry and
requeue remain technical Admin operations until their owner workflow has
consumer-specific impact analysis, idempotence and audit.
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from core.models import DomainEventConsumption, DomainEventOutbox


def operator_event_status(actor):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.PLATFORM_MANAGE):
        raise PermissionDenied("Autorité système Platform requise.")
    event_counts = {
        row["status"]: row["total"]
        for row in DomainEventOutbox.objects.values("status").annotate(total=Count("id"))
    }
    consumption_counts = {
        row["status"]: row["total"]
        for row in DomainEventConsumption.objects.values("status").annotate(total=Count("id"))
    }
    affected = (
        DomainEventConsumption.objects.filter(status="failed")
        .select_related("event").order_by("-updated_at")[:30]
    )
    return {
        "observed_at": timezone.now(),
        "event_counts": event_counts,
        "consumption_counts": consumption_counts,
        "failures": [
            {
                "event_id": str(row.event_id),
                "event_type": row.event.event_type,
                "consumer": row.consumer,
                "attempts": row.attempts,
                "max_attempts": row.max_attempts,
                "status": row.status,
                "last_changed": row.updated_at,
            } for row in affected
        ],
        "coverage": "Outbox et consommations Domain Events uniquement",
        "requeue_available": False,
    }
