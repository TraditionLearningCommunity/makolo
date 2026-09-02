from __future__ import annotations

from django.utils import timezone

from activities.models import OccurrenceStatus
from journeys.collaboration_models import TERMINAL_STEP_STATUSES

from .hazards import get_action_advices, get_hazards
from .mobility import get_mobility_context
from .spatial import get_spatial_context
from .temporal import get_temporal_context


def next_journey_occurrence(journey, *, now=None):
    now = now or timezone.now()
    candidate_steps = []
    for step in journey.steps.all():
        if step.status in TERMINAL_STEP_STATUSES or step.occurrence_id is None:
            continue
        occurrence = step.occurrence
        if occurrence.status == OccurrenceStatus.CANCELLED:
            candidate_steps.append(occurrence)
        elif occurrence.end_at is None or occurrence.end_at > now:
            candidate_steps.append(occurrence)
    if candidate_steps:
        candidate_steps.sort(key=lambda item: (item.start_at, str(item.pk)))
        return candidate_steps[0]
    return journey.occurrence


def get_journey_spatiotemporal_context(journey, *, origin=None, now=None, providers=None):
    now = now or timezone.now()
    occurrence = next_journey_occurrence(journey, now=now)
    if occurrence is None:
        return None
    temporal = get_temporal_context(occurrence, now=now)
    spatial = get_spatial_context(occurrence, origin=origin)
    # start_at is the transparent generic fallback target. Verticals may call
    # get_mobility_context with an earlier policy-derived target_arrival.
    target_arrival = occurrence.start_at
    mobility = get_mobility_context(
        occurrence,
        origin=origin,
        target_arrival=target_arrival,
        now=now,
        providers=providers,
    )
    hazards = get_hazards(
        occurrence=occurrence,
        journey=journey,
        mobility=mobility,
        now=now,
    )
    advices = get_action_advices(
        occurrence=occurrence,
        journey=journey,
        mobility=mobility,
        hazards=hazards,
        now=now,
    )
    return {
        "occurrence": occurrence,
        "temporal": temporal,
        "spatial": spatial,
        "mobility": mobility,
        "hazards": hazards,
        "advices": advices,
    }
