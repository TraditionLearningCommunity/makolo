from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES

from .context import get_journey_spatiotemporal_context


@dataclass(frozen=True)
class PersonalActionProjection:
    key: str
    occurred_at: object
    title: str
    summary: str
    reason_code: str
    cta_label: str
    cta_url: str
    activity: object


def personal_action_projections(profile, *, origin=None, at=None, limit=5):
    """Journey-private M6 projections for the owner's personal Action Stream.

    `leave_soon` requires an explicit origin and a provider-backed departure
    recommendation. Without those inputs no departure item is fabricated.
    """
    if not getattr(profile, "is_authenticated", False):
        return ()
    at = at or timezone.now()
    journeys = (
        Journey.objects.filter(beneficiary=profile)
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .filter(occurrence__isnull=False)
        .select_related("activity", "occurrence")
        .prefetch_related("occurrence__place_links__place", "steps__occurrence__place_links__place", "accesses")
        .order_by("occurrence__start_at", "id")[: max(1, int(limit))]
    )
    rows = []
    for journey in journeys:
        context = get_journey_spatiotemporal_context(journey, origin=origin, now=at)
        if context is None:
            continue
        for advice in context["advices"]:
            if advice.reason_code not in {"leave_soon", "occurrence_cancelled", "access_unavailable"}:
                continue
            rows.append(PersonalActionProjection(
                key=f"m6-journey:{journey.pk}:{advice.reason_code}",
                occurred_at=advice.observed_at,
                title=journey.activity.title,
                summary=advice.summary,
                reason_code=advice.reason_code,
                cta_label="Ouvrir la démarche",
                cta_url=advice.action_url or reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                activity=journey.activity,
            ))
    return tuple(rows)
