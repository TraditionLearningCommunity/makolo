from collections import Counter

from access.models import Access, AccessStatus
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.selectors import capacity_availability, pools_for_occurrence
from journeys.models import Journey
from readiness import ReadinessCheck, ReadinessCheckState, ReadinessResult, ReadinessStatus, reduce_readiness_status
from scanner.models import ScannerAssignment
from spatiotemporal.hazards import get_action_advices, get_hazards
from spatiotemporal.mobility import get_mobility_context
from spatiotemporal.operations import scanner_operational_hazards
from spatiotemporal.spatial import get_spatial_context
from spatiotemporal.temporal import get_temporal_context
from spatiotemporal.types import TemporalState

from .checkpoint_selectors import (
    active_checkpoint_assignments,
    next_checkpoint,
    observations_for_beneficiary,
    ordered_checkpoints,
    profile_is_checkpoint_beneficiary,
)
from .models import PlacementPlan, QueueEntryStatus
from .operational_readiness import resolve_operational_readiness
from .permissions import user_can_manage_activity_operations, user_can_view_activity_operations
from .placement_selectors import get_profile_occurrence_placements
from .queue_selectors import my_queue_entries, queue_position, queue_snapshot, queues_for_occurrence


_INELIGIBLE_JOURNEY_STATUSES = {"rejected", "cancelled", "expired"}
_PARTICIPANT_SAFE_PREFIXES = (
    "operations.occurrence",
    "operations.checkpoints",
    "operations.queue",
    "operations.spatial",
)


def occurrence_live_phase(occurrence, *, now=None):
    state = get_temporal_context(occurrence, now=now).state
    return {
        TemporalState.UPCOMING: "before",
        TemporalState.SOON: "arrival",
        TemporalState.ACTIVE: "live",
        TemporalState.ENDED: "after",
        TemporalState.CANCELLED: "cancelled",
    }[state]


def resolve_live_perspective(*, actor, occurrence):
    if not actor or not getattr(actor, "is_authenticated", False):
        return None
    if user_can_view_activity_operations(actor, occurrence.activity):
        if occurrence.activity.space_id and (
            can(actor, PermissionCode.SPACE_ACTIVITIES_VIEW, occurrence.activity.space)
            or can(actor, PermissionCode.SPACE_MANAGE, occurrence.activity.space)
        ):
            return "space"
        return "operator"
    if profile_is_checkpoint_beneficiary(actor, occurrence):
        return "participant"
    return None


def _readiness_payload(result):
    return {
        "state": result.status.value,
        "observed_at": result.observed_at,
        "contributors": [
            {
                "key": check.key,
                "state": check.state.value,
                "reason": check.reason_code,
                "source": check.source,
                "message": check.summary,
                "next_action": (
                    {
                        "type": check.next_action.key,
                        "label": check.next_action.label,
                        "source": check.next_action.source,
                        "url": check.next_action.url,
                    }
                    if check.next_action
                    else None
                ),
            }
            for check in result.checks
        ],
        "next_action": (
            {
                "type": result.next_action.key,
                "label": result.next_action.label,
                "source": result.next_action.source,
                "url": result.next_action.url,
            }
            if result.next_action
            else None
        ),
    }


def _participant_journey(actor, occurrence):
    return (
        Journey.objects.filter(beneficiary=actor, activity=occurrence.activity, occurrence=occurrence)
        .exclude(status__in=_INELIGIBLE_JOURNEY_STATUSES)
        .order_by("created_at", "id")
        .first()
    )


def _participant_accesses(actor, occurrence):
    return list(
        Access.objects.filter(beneficiary=actor, activity=occurrence.activity, occurrence=occurrence)
        .only("id", "status", "valid_from", "valid_until")
        .order_by("created_at", "id")
    )


def _access_usable(access, now):
    if access.status not in {AccessStatus.VALID, AccessStatus.USED}:
        return False
    if access.valid_from and access.valid_from > now:
        return False
    if access.valid_until and access.valid_until <= now:
        return False
    return True


def _participant_specific_checks(*, actor, occurrence, now):
    checks = []
    accesses = _participant_accesses(actor, occurrence)
    if not accesses:
        checks.append(
            ReadinessCheck(
                key="operations.access.me",
                source="access.access",
                state=ReadinessCheckState.NOT_APPLICABLE,
                blocking=False,
                reason_code="participant_access_not_used",
                summary="Aucun Access spécifique n’est requis pour ce participant.",
            )
        )
    elif any(_access_usable(access, now) for access in accesses):
        checks.append(
            ReadinessCheck(
                key="operations.access.me",
                source="access.access",
                state=ReadinessCheckState.SATISFIED,
                blocking=False,
                reason_code="participant_access_ready",
                summary="Votre accès est exploitable.",
            )
        )
    elif any(access.status == AccessStatus.PENDING for access in accesses):
        checks.append(
            ReadinessCheck(
                key="operations.access.me",
                source="access.access",
                state=ReadinessCheckState.WAITING,
                blocking=False,
                reason_code="participant_access_pending",
                summary="Votre accès est encore en préparation.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                key="operations.access.me",
                source="access.access",
                state=ReadinessCheckState.BLOCKING,
                blocking=True,
                reason_code="participant_access_unavailable",
                summary="Votre accès n’est pas exploitable pour cette occurrence.",
            )
        )

    required_plans = list(PlacementPlan.objects.filter(occurrence=occurrence, active=True, required=True))
    if not required_plans:
        checks.append(
            ReadinessCheck(
                key="operations.placement.me",
                source="operations.placement",
                state=ReadinessCheckState.NOT_APPLICABLE,
                blocking=False,
                reason_code="participant_placement_not_required",
                summary="Aucun placement obligatoire ne vous concerne.",
            )
        )
    else:
        placements = list(get_profile_occurrence_placements(actor, occurrence))
        placed_plan_ids = {row.plan_id for row in placements}
        missing = [plan for plan in required_plans if plan.pk not in placed_plan_ids]
        if missing:
            checks.append(
                ReadinessCheck(
                    key="operations.placement.me",
                    source="operations.placement",
                    state=ReadinessCheckState.ACTION_REQUIRED,
                    blocking=False,
                    reason_code="participant_placement_missing",
                    summary="Un placement obligatoire n’est pas encore attribué.",
                )
            )
        else:
            checks.append(
                ReadinessCheck(
                    key="operations.placement.me",
                    source="operations.placement",
                    state=ReadinessCheckState.SATISFIED,
                    blocking=False,
                    reason_code="participant_placement_ready",
                    summary="Votre placement obligatoire est disponible.",
                )
            )
    return checks


def participant_readiness_projection(*, actor, occurrence, operational_result, now):
    safe = [
        check
        for check in operational_result.checks
        if check.key.startswith(_PARTICIPANT_SAFE_PREFIXES)
    ]
    checks = safe + _participant_specific_checks(actor=actor, occurrence=occurrence, now=now)
    status = reduce_readiness_status(checks)
    phase = occurrence_live_phase(occurrence, now=now)
    if status == ReadinessStatus.READY and phase == "after":
        status = ReadinessStatus.COMPLETE
    next_action = next(
        (
            check.next_action
            for state in (ReadinessCheckState.BLOCKING, ReadinessCheckState.ACTION_REQUIRED, ReadinessCheckState.WAITING)
            for check in checks
            if check.state == state and check.next_action
        ),
        None,
    )
    return ReadinessResult(status=status, checks=tuple(checks), next_action=next_action, observed_at=operational_result.observed_at)


def _occurrence_payload(occurrence):
    return {
        "id": occurrence.pk,
        "activity_id": occurrence.activity_id,
        "label": occurrence.label,
        "status": occurrence.status,
    }


def _timing_payload(occurrence, now):
    temporal = get_temporal_context(occurrence, now=now)
    return {
        "start_at": occurrence.start_at,
        "end_at": occurrence.end_at,
        "timezone": occurrence.timezone,
        "temporal_state": temporal.state.value,
    }


def _participant_access_payload(actor, occurrence, now):
    return [
        {
            "id": access.pk,
            "status": access.status,
            "usable": _access_usable(access, now),
            "valid_from": access.valid_from,
            "valid_until": access.valid_until,
        }
        for access in _participant_accesses(actor, occurrence)
    ]


def _participant_placement_payload(actor, occurrence):
    return [
        {
            "plan_id": assignment.plan_id,
            "plan": assignment.plan.label,
            "unit_id": assignment.unit_id,
            "unit": assignment.unit.label,
            "parent_unit": assignment.unit.parent.label if assignment.unit.parent_id else None,
        }
        for assignment in get_profile_occurrence_placements(actor, occurrence)
    ]


def _participant_flow_payload(actor, occurrence):
    completed = set(
        observations_for_beneficiary(occurrence=occurrence, profile=actor).values_list("checkpoint_id", flat=True)
    )
    checkpoints = list(ordered_checkpoints(occurrence=occurrence))
    next_result = next_checkpoint(occurrence=occurrence, profile=actor)
    return {
        "checkpoints": [
            {
                "id": checkpoint.pk,
                "key": checkpoint.key,
                "label": checkpoint.label,
                "required": checkpoint.required,
                "status": checkpoint.status,
                "completed": checkpoint.pk in completed,
            }
            for checkpoint in checkpoints
        ],
        "next_checkpoint": (
            {
                "id": next_result.checkpoint.pk,
                "label": next_result.checkpoint.label,
                "status": next_result.checkpoint.status,
                "blocked_reason": next_result.blocked_reason or None,
            }
            if next_result.checkpoint
            else None
        ),
    }


def _participant_queue_payload(actor, occurrence):
    rows = []
    for entry in my_queue_entries(profile=actor, occurrence=occurrence):
        rows.append(
            {
                "id": entry.pk,
                "queue_id": entry.queue_id,
                "label": entry.queue.label,
                "checkpoint_id": entry.queue.checkpoint_id,
                "status": entry.status,
                "position": queue_position(entry=entry),
                "called_at": entry.called_at,
            }
        )
    return rows


def _participant_capacity_payload(occurrence, now):
    rows = []
    for pool in pools_for_occurrence(occurrence).filter(is_active=True):
        availability = capacity_availability(pool, now=now)
        rows.append(
            {
                "id": pool.pk,
                "label": pool.label,
                "unlimited": availability.unlimited,
                "available": availability.available,
            }
        )
    return rows


def _spatial_payload(*, occurrence, journey, now, include_operator_hazards=False):
    spatial = get_spatial_context(occurrence)
    mobility = get_mobility_context(occurrence, target_arrival=occurrence.start_at, now=now)
    hazards = list(get_hazards(occurrence=occurrence, journey=journey, mobility=mobility, now=now))
    if include_operator_hazards:
        hazards.extend(scanner_operational_hazards(occurrence, now=now))
    advices = get_action_advices(occurrence=occurrence, journey=journey, mobility=mobility, hazards=hazards, now=now)
    return {
        "place": (
            {"id": spatial.place.pk, "name": spatial.place.name}
            if spatial.place is not None
            else None
        ),
        "zone": (
            {"id": spatial.zone.pk, "name": spatial.zone.name}
            if spatial.zone is not None
            else None
        ),
        "mobility": {
            "status": mobility.status,
            "recommended_departure": mobility.recommended_departure,
            "itinerary_url": mobility.itinerary_url,
        },
        "hazards": [
            {
                "kind": hazard.kind,
                "severity": hazard.severity.value,
                "summary": hazard.summary,
                "source": hazard.source,
            }
            for hazard in hazards
        ],
        "advices": [
            {
                "type": advice.kind,
                "reason": advice.reason_code,
                "label": advice.summary,
                "source": advice.source_key,
                "url": advice.action_url or None,
            }
            for advice in advices
        ],
    }


def _participant_next_action(*, occurrence, phase, accesses, placements, flow, queues, spatial):
    if phase == "cancelled":
        return {"type": "none", "source": "activities.occurrence", "reason": "occurrence_cancelled", "label": "Aucune opération live — occurrence annulée."}
    if phase == "after":
        return {"type": "none", "source": "activities.occurrence", "reason": "occurrence_completed", "label": "Cette occurrence est terminée."}

    called = next((row for row in queues if row["status"] == QueueEntryStatus.CALLED), None)
    if called:
        checkpoint = next((row for row in flow["checkpoints"] if row["id"] == called["checkpoint_id"]), None)
        label = checkpoint["label"] if checkpoint else called["label"]
        return {
            "type": "queue_called",
            "source": "operations.queue",
            "reason": "queue_entry_called",
            "checkpoint_id": called["checkpoint_id"],
            "label": f"C’est votre tour. Présentez-vous maintenant à {label}.",
        }

    if accesses and not any(row["usable"] for row in accesses):
        return {"type": "access", "source": "access.access", "reason": "participant_access_unavailable", "label": "Régularisez votre accès avant de poursuivre."}

    next_cp = flow["next_checkpoint"]
    if next_cp and next_cp["blocked_reason"]:
        return {
            "type": "checkpoint_wait",
            "source": "operations.flow",
            "reason": f"next_checkpoint_{next_cp['blocked_reason']}",
            "checkpoint_id": next_cp["id"],
            "label": f"Attendez les instructions pour {next_cp['label']}.",
        }

    waiting = next((row for row in queues if row["status"] == QueueEntryStatus.WAITING), None)
    if waiting:
        checkpoint = next((row for row in flow["checkpoints"] if row["id"] == waiting["checkpoint_id"]), None)
        label = checkpoint["label"] if checkpoint else waiting["label"]
        return {
            "type": "queue_wait",
            "source": "operations.queue",
            "reason": "queue_entry_waiting",
            "checkpoint_id": waiting["checkpoint_id"],
            "label": f"Restez disponible près de {label}.",
        }

    if next_cp:
        return {
            "type": "checkpoint",
            "source": "operations.flow",
            "reason": "next_required_checkpoint",
            "checkpoint_id": next_cp["id"],
            "label": f"Rejoignez {next_cp['label']}.",
        }

    if placements:
        placement = placements[0]
        label = " · ".join(value for value in [placement["parent_unit"], placement["unit"]] if value)
        return {"type": "placement", "source": "operations.placement", "reason": "placement_available", "label": f"Rejoignez {label}."}

    if spatial["advices"]:
        return spatial["advices"][0]
    return {"type": "none", "source": "operations.live", "reason": "no_immediate_action", "label": "Aucune action immédiate."}


def _operator_checkpoints(occurrence):
    rows = []
    for checkpoint in ordered_checkpoints(occurrence=occurrence):
        assignments = list(active_checkpoint_assignments(checkpoint=checkpoint))
        authorized = sum(
            1 for assignment in assignments if user_can_manage_activity_operations(assignment.profile, occurrence.activity)
        )
        rows.append(
            {
                "id": checkpoint.pk,
                "key": checkpoint.key,
                "label": checkpoint.label,
                "required": checkpoint.required,
                "status": checkpoint.status,
                "assignment_count": len(assignments),
                "authorized_assignment_count": authorized,
            }
        )
    return rows


def _operator_queues(occurrence, now):
    return [
        {
            "id": queue.pk,
            "label": queue.label,
            "status": queue.status,
            "checkpoint_id": queue.checkpoint_id,
            "counts": queue_snapshot(queue=queue, now=now),
        }
        for queue in queues_for_occurrence(occurrence=occurrence)
    ]


def _operator_capacity(occurrence, now):
    rows = []
    for pool in pools_for_occurrence(occurrence).filter(is_active=True):
        availability = capacity_availability(pool, now=now)
        rows.append(
            {
                "id": pool.pk,
                "label": pool.label,
                "total": availability.total,
                "held": availability.held,
                "committed": availability.committed,
                "available": availability.available,
                "unlimited": availability.unlimited,
            }
        )
    return rows


def _operator_placements(occurrence):
    return [
        {
            "id": plan.pk,
            "key": plan.key,
            "label": plan.label,
            "required": plan.required,
            "active_assignment_count": plan.assignments.filter(ended_at__isnull=True).count(),
        }
        for plan in PlacementPlan.objects.filter(occurrence=occurrence, active=True).order_by("label", "id")
    ]


def _operator_access(occurrence):
    statuses = Counter(
        Access.objects.filter(activity=occurrence.activity, occurrence=occurrence).values_list("status", flat=True)
    )
    return {"total": sum(statuses.values()), "by_status": dict(statuses)}


def _scanner_current(assignment, now):
    return bool(
        assignment.is_active
        and (assignment.valid_from is None or assignment.valid_from <= now)
        and (assignment.valid_until is None or assignment.valid_until > now)
    )


def _operator_scanner(occurrence, now):
    assignments = list(
        ScannerAssignment.objects.filter(activity=occurrence.activity, occurrence=occurrence).select_related("agent")
    )
    current = [assignment for assignment in assignments if _scanner_current(assignment, now)]
    authorized = [
        assignment
        for assignment in current
        if can(assignment.agent, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=occurrence.activity, at=now)
    ]
    return {
        "configured": len(assignments),
        "current": len(current),
        "authorized": len(authorized),
    }


def _operator_next_action(readiness, phase):
    if phase == "cancelled":
        return {"type": "none", "source": "activities.occurrence", "reason": "occurrence_cancelled", "label": "Aucune opération live — occurrence annulée."}
    if phase == "after":
        return {"type": "none", "source": "activities.occurrence", "reason": "occurrence_completed", "label": "Aucune action live : occurrence terminée."}
    if readiness.next_action:
        return {
            "type": readiness.next_action.key,
            "source": readiness.next_action.source,
            "reason": next((check.reason_code for check in readiness.checks if check.next_action == readiness.next_action), "readiness_action"),
            "label": readiness.next_action.label,
            "url": readiness.next_action.url,
        }
    return {"type": "none", "source": "operations.readiness", "reason": "no_corrective_action", "label": "Aucune action corrective urgente."}


def resolve_occurrence_live(*, occurrence, actor, observed_at=None):
    from django.utils import timezone

    now = observed_at or timezone.now()
    perspective = resolve_live_perspective(actor=actor, occurrence=occurrence)
    if perspective is None:
        return None
    phase = occurrence_live_phase(occurrence, now=now)
    operational = resolve_operational_readiness(occurrence, viewer=actor, observed_at=now)
    base = {
        "perspective": perspective,
        "occurrence": _occurrence_payload(occurrence),
        "timing": _timing_payload(occurrence, now),
        "phase": phase,
    }

    if perspective == "participant":
        journey = _participant_journey(actor, occurrence)
        participant_readiness = participant_readiness_projection(
            actor=actor,
            occurrence=occurrence,
            operational_result=operational,
            now=now,
        )
        accesses = _participant_access_payload(actor, occurrence, now)
        placements = _participant_placement_payload(actor, occurrence)
        flow = _participant_flow_payload(actor, occurrence)
        queues = _participant_queue_payload(actor, occurrence)
        spatial = _spatial_payload(occurrence=occurrence, journey=journey, now=now)
        base.update(
            {
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
        )
        return base

    spatial = _spatial_payload(occurrence=occurrence, journey=None, now=now, include_operator_hazards=True)
    base.update(
        {
            "access": _operator_access(occurrence),
            "placement": _operator_placements(occurrence),
            "checkpoints": _operator_checkpoints(occurrence),
            "queue": _operator_queues(occurrence, now),
            "capacity": _operator_capacity(occurrence, now),
            "scanner": _operator_scanner(occurrence, now),
            "spatial": spatial,
            "operational_readiness": _readiness_payload(operational),
            "next_action": _operator_next_action(operational, phase),
        }
    )
    return base


def resolve_occurrence_readiness_for_viewer(*, occurrence, actor, observed_at=None):
    from django.utils import timezone

    now = observed_at or timezone.now()
    perspective = resolve_live_perspective(actor=actor, occurrence=occurrence)
    if perspective is None:
        return None
    operational = resolve_operational_readiness(occurrence, viewer=actor, observed_at=now)
    if perspective == "participant":
        operational = participant_readiness_projection(
            actor=actor,
            occurrence=occurrence,
            operational_result=operational,
            now=now,
        )
    return {"perspective": perspective, **_readiness_payload(operational)}
