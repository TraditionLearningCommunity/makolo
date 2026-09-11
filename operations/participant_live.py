"""Participant-specific Occurrence Live projection.

The generic Operations live resolver deliberately chooses an operational
perspective when a Profile also holds operator authority. Personal `/me/`
surfaces need the opposite contract: if the Profile is an eligible
beneficiary, return only the participant-safe projection regardless of any
additional authority they may hold.

This module owns no business state. It composes the same canonical Operations,
Access, Placement, Queue, Capacity and M6 selectors used by occurrence_live.
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
    """Return the participant-safe live projection or ``None`` when ineligible.

    This is intentionally independent from operator/Space perspective
    resolution. Holding additional authority must never make a personal route
    expose operator data or become unavailable to the same participant.
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
