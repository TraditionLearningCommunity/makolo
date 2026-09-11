"""Explicit participant-safe Occurrence Live projection for personal surfaces.

The generic Operations resolver selects the actor's operational perspective and
therefore legitimately prefers operator/Space authority when a Profile has
multiple roles. Personal `/me/` surfaces need the opposite contract: they must
ask explicitly for the participant projection and validate beneficiary scope.
This module composes the canonical Operations selectors without introducing
new persistent state or a second business truth.
"""

from django.utils import timezone

from .checkpoint_selectors import profile_is_checkpoint_beneficiary
from .occurrence_live import (
    _occurrence_payload,
    _participant_access_payload,
    _participant_capacity_payload,
    _participant_flow_payload,
    _participant_journey,
    _participant_next_action,
    _participant_placement_payload,
    _participant_queue_payload,
    _readiness_payload,
    _spatial_payload,
    _timing_payload,
    occurrence_live_phase,
    participant_readiness_projection,
)
from .operational_readiness import resolve_operational_readiness


def resolve_participant_occurrence_live(*, occurrence, actor, observed_at=None):
    """Return the participant projection only when ``actor`` is a beneficiary.

    Operator/Space permissions never widen this personal scope. A Profile that
    is both an operator and a participant still receives participant-safe data
    here; generic Operations surfaces continue to use ``resolve_occurrence_live``.
    """
    if not actor or not getattr(actor, "is_authenticated", False):
        return None
    if not profile_is_checkpoint_beneficiary(actor, occurrence):
        return None

    now = observed_at or timezone.now()
    phase = occurrence_live_phase(occurrence, now=now)
    operational = resolve_operational_readiness(occurrence, viewer=actor, observed_at=now)
    participant_readiness = participant_readiness_projection(
        actor=actor,
        occurrence=occurrence,
        operational_result=operational,
        now=now,
    )
    journey = _participant_journey(actor, occurrence)
    accesses = _participant_access_payload(actor, occurrence, now)
    placements = _participant_placement_payload(actor, occurrence)
    flow = _participant_flow_payload(actor, occurrence)
    queues = _participant_queue_payload(actor, occurrence)
    spatial = _spatial_payload(occurrence=occurrence, journey=journey, now=now)

    return {
        "perspective": "participant",
        "occurrence": _occurrence_payload(occurrence),
        "timing": _timing_payload(occurrence, now),
        "phase": phase,
        "access": accesses,
        "placement": placements,
        "flow": flow,
        "queue": queues,
        "capacity": _participant_capacity_payload(occurrence, now),
        "spatial": spatial,
        "operational_readiness": _readiness_payload(participant_readiness),
        "next_action": _participant_next_action(
            occurrence=occurrence,
            phase=phase,
            accesses=accesses,
            placements=placements,
            flow=flow,
            queues=queues,
            spatial=spatial,
        ),
    }
