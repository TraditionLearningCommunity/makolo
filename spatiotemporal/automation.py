from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES

from .notifications import notify_significant_journey_hazards


def automation_horizon() -> timedelta:
    return timedelta(
        hours=int(getattr(settings, "SPATIOTEMPORAL_AUTOMATION_HORIZON_HOURS", 24))
    )


def reevaluate_journey_hazards(*, now=None, limit=200):
    """Reevaluate high-value Journey hazards inside the existing Autopilot cadence.

    This selector is deliberately bounded and provider-free: it uses canonical
    Occurrence/Access facts only, never requests GPS, and relies on Notification
    dedup keys for idempotence. External routing/weather reevaluation remains a
    detailed-context concern until a real provider policy exists.
    """
    now = now or timezone.now()
    horizon = now + automation_horizon()
    journeys = list(
        Journey.objects.filter(
            beneficiary__isnull=False,
            occurrence__isnull=False,
            occurrence__start_at__lte=horizon,
        )
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .select_related("beneficiary", "activity", "occurrence")
        .prefetch_related(
            "accesses",
            "occurrence__place_links__place",
            "steps__occurrence__place_links__place",
        )
        .order_by("occurrence__start_at", "id")[:limit]
    )

    notifications = set()
    for journey in journeys:
        for notification in notify_significant_journey_hazards(journey, now=now):
            notifications.add(notification.pk)
    return {
        "journeys_checked": len(journeys),
        "hazard_notifications": len(notifications),
    }


def run_spatiotemporal_automation_cycle(*, now=None, limit=200):
    return reevaluate_journey_hazards(now=now, limit=limit)
