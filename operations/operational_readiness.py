from access.models import Access, AccessStatus
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.selectors import capacity_availability, pools_for_occurrence
from journeys.models import Journey
from readiness import NextAction, ReadinessCheck, ReadinessCheckState, ReadinessStatus, resolve_readiness
from readiness.registry import registry
from scanner.models import ScannerAssignment
from spatiotemporal.hazards import get_hazards
from spatiotemporal.mobility import get_mobility_context
from spatiotemporal.spatial import get_spatial_context
from spatiotemporal.temporal import get_temporal_context
from spatiotemporal.types import HazardSeverity, TemporalState

from .checkpoint_selectors import active_checkpoint_assignments, ordered_checkpoints
from .models import CheckpointStatus, PlacementAssignment, PlacementPlan, QueueEntryStatus, QueueStatus
from .permissions import user_can_manage_activity_operations
from .queue_selectors import queues_for_occurrence


OPERATIONS_READINESS_CONTEXT = "operations"
_INELIGIBLE_JOURNEY_STATUSES = {"rejected", "cancelled", "expired"}


def _check(key, source, state, reason_code, summary, *, blocking=False, action=None):
    return ReadinessCheck(
        key=key,
        source=source,
        state=state,
        blocking=blocking,
        reason_code=reason_code,
        summary=summary,
        next_action=action,
    )


def _action(key, label, source):
    return NextAction(key=key, label=label, source=source)


def _operational_status_for(checks, occurrence, now):
    from readiness import reduce_readiness_status

    status = reduce_readiness_status(checks)
    if status != ReadinessStatus.READY:
        return status
    temporal = get_temporal_context(occurrence, now=now)
    if occurrence.status == "completed" or temporal.state == TemporalState.ENDED:
        return ReadinessStatus.COMPLETE
    return ReadinessStatus.READY


def _eligible_journeys(occurrence):
    return Journey.objects.filter(activity=occurrence.activity, occurrence=occurrence).exclude(
        status__in=_INELIGIBLE_JOURNEY_STATUSES
    )


def _access_is_usable(access, now):
    if access.status not in {AccessStatus.VALID, AccessStatus.USED}:
        return False
    if access.valid_from and access.valid_from > now:
        return False
    if access.valid_until and access.valid_until <= now:
        return False
    return True


def _scanner_assignment_is_current(assignment, now):
    if not assignment.is_active:
        return False
    if assignment.valid_from and assignment.valid_from > now:
        return False
    if assignment.valid_until and assignment.valid_until <= now:
        return False
    return True


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_occurrence_contributor(occurrence, viewer, now):
    temporal = get_temporal_context(occurrence, now=now)
    if occurrence.status == "cancelled" or temporal.state == TemporalState.CANCELLED:
        return [
            _check(
                "operations.occurrence",
                "activities.occurrence",
                ReadinessCheckState.BLOCKING,
                "occurrence_cancelled",
                "L’occurrence est annulée et ne peut pas être exécutée en live.",
                blocking=True,
            )
        ]
    if occurrence.status == "draft":
        return [
            _check(
                "operations.occurrence",
                "activities.occurrence",
                ReadinessCheckState.BLOCKING,
                "occurrence_not_scheduled",
                "L’occurrence est encore en brouillon.",
                blocking=True,
                action=_action("schedule_occurrence", "Planifier l’occurrence", "activities.occurrence"),
            )
        ]
    if occurrence.status == "completed" or temporal.state == TemporalState.ENDED:
        return [
            _check(
                "operations.occurrence",
                "activities.occurrence",
                ReadinessCheckState.SATISFIED,
                "occurrence_completed",
                "L’occurrence est terminée.",
            )
        ]
    return [
        _check(
            "operations.occurrence",
            "activities.occurrence",
            ReadinessCheckState.SATISFIED,
            "occurrence_operational",
            "Le cycle de vie de l’occurrence permet son suivi opérationnel.",
        )
    ]


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_access_contributor(occurrence, viewer, now):
    accesses = list(
        Access.objects.filter(activity=occurrence.activity)
        .filter(occurrence=occurrence)
        .only("id", "status", "valid_from", "valid_until")
    )
    if not accesses:
        return [
            _check(
                "operations.access",
                "access.access",
                ReadinessCheckState.NOT_APPLICABLE,
                "access_not_used",
                "Aucun Access spécifique n’est configuré pour cette occurrence.",
            )
        ]
    usable = [access for access in accesses if _access_is_usable(access, now)]
    if usable:
        unusable_count = len(accesses) - len(usable)
        if unusable_count:
            return [
                _check(
                    "operations.access",
                    "access.access",
                    ReadinessCheckState.ACTION_REQUIRED,
                    "some_access_unavailable",
                    f"{unusable_count} droit(s) d’accès ne sont pas actuellement exploitables.",
                    action=_action("review_access", "Vérifier les accès indisponibles", "access.access"),
                )
            ]
        return [
            _check(
                "operations.access",
                "access.access",
                ReadinessCheckState.SATISFIED,
                "access_operational",
                "Les droits Access configurés sont exploitables.",
            )
        ]
    if any(access.status == AccessStatus.PENDING for access in accesses):
        return [
            _check(
                "operations.access",
                "access.access",
                ReadinessCheckState.WAITING,
                "access_pending",
                "Les droits Access configurés sont encore en préparation.",
                action=_action("review_access", "Vérifier la préparation des accès", "access.access"),
            )
        ]
    return [
        _check(
            "operations.access",
            "access.access",
            ReadinessCheckState.BLOCKING,
            "access_unavailable",
            "Aucun droit Access configuré n’est actuellement exploitable.",
            blocking=True,
            action=_action("restore_access", "Régulariser les accès requis", "access.access"),
        )
    ]


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_capacity_contributor(occurrence, viewer, now):
    pools = list(pools_for_occurrence(occurrence).filter(is_active=True))
    if not pools:
        return [
            _check(
                "operations.capacity",
                "capacity.pool",
                ReadinessCheckState.NOT_APPLICABLE,
                "capacity_not_used",
                "Aucun pool Capacity n’est configuré pour cette occurrence.",
            )
        ]
    checks = []
    for pool in pools:
        availability = capacity_availability(pool, now=now)
        label = pool.label or "Capacité"
        used = availability.held + availability.committed
        if availability.total is not None and used > availability.total:
            checks.append(
                _check(
                    f"operations.capacity.{pool.pk}",
                    "capacity.pool",
                    ReadinessCheckState.BLOCKING,
                    "capacity_overcommitted",
                    f"{label} dépasse la capacité canonique configurée.",
                    blocking=True,
                    action=_action("review_capacity", f"Vérifier {label}", "capacity.pool"),
                )
            )
        elif availability.sold_out:
            checks.append(
                _check(
                    f"operations.capacity.{pool.pk}",
                    "capacity.pool",
                    ReadinessCheckState.ACTION_REQUIRED,
                    "capacity_exhausted",
                    f"{label} n’a plus de capacité disponible.",
                    action=_action("review_capacity", f"Vérifier {label}", "capacity.pool"),
                )
            )
        else:
            checks.append(
                _check(
                    f"operations.capacity.{pool.pk}",
                    "capacity.pool",
                    ReadinessCheckState.SATISFIED,
                    "capacity_available",
                    f"{label} reste exploitable.",
                )
            )
    return checks


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_placement_contributor(occurrence, viewer, now):
    plans = list(PlacementPlan.objects.filter(occurrence=occurrence, active=True).order_by("label", "id"))
    if not plans:
        return [
            _check(
                "operations.placement",
                "operations.placement",
                ReadinessCheckState.NOT_APPLICABLE,
                "placement_not_used",
                "Aucun PlacementPlan n’est utilisé pour cette occurrence.",
            )
        ]
    required = [plan for plan in plans if plan.required]
    if not required:
        return [
            _check(
                "operations.placement",
                "operations.placement",
                ReadinessCheckState.NOT_APPLICABLE,
                "placement_optional",
                "Les plans de placement configurés sont optionnels.",
            )
        ]
    journeys = list(_eligible_journeys(occurrence).values_list("beneficiary_id", "external_beneficiary_id"))
    expected_profiles = {profile_id for profile_id, _ in journeys if profile_id}
    expected_external = {external_id for _, external_id in journeys if external_id}
    checks = []
    for plan in required:
        assignments = PlacementAssignment.objects.filter(plan=plan, ended_at__isnull=True)
        placed_profiles = set(assignments.exclude(profile_id=None).values_list("profile_id", flat=True))
        placed_external = set(assignments.exclude(external_beneficiary_id=None).values_list("external_beneficiary_id", flat=True))
        missing = len(expected_profiles - placed_profiles) + len(expected_external - placed_external)
        if missing:
            checks.append(
                _check(
                    f"operations.placement.{plan.pk}",
                    "operations.placement",
                    ReadinessCheckState.BLOCKING,
                    "required_placement_incomplete",
                    f"{missing} bénéficiaire(s) attendu(s) n’ont pas de placement dans « {plan.label} ».",
                    blocking=True,
                    action=_action("complete_placement", f"Compléter {plan.label}", "operations.placement"),
                )
            )
        else:
            checks.append(
                _check(
                    f"operations.placement.{plan.pk}",
                    "operations.placement",
                    ReadinessCheckState.SATISFIED,
                    "required_placement_complete",
                    f"Le plan requis « {plan.label} » est complet pour les bénéficiaires attendus.",
                )
            )
    return checks


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_checkpoints_contributor(occurrence, viewer, now):
    temporal = get_temporal_context(occurrence, now=now)
    checkpoints = list(ordered_checkpoints(occurrence=occurrence).filter(required=True))
    if not checkpoints:
        return [
            _check(
                "operations.checkpoints",
                "operations.checkpoints",
                ReadinessCheckState.NOT_APPLICABLE,
                "checkpoints_not_used",
                "Aucun checkpoint obligatoire n’est configuré.",
            )
        ]
    if temporal.state == TemporalState.ENDED or occurrence.status == "completed":
        return [
            _check(
                "operations.checkpoints",
                "operations.checkpoints",
                ReadinessCheckState.SATISFIED,
                "checkpoint_execution_finished",
                "L’exécution des checkpoints est terminée avec l’occurrence.",
            )
        ]
    checks = []
    for checkpoint in checkpoints:
        key = f"operations.checkpoints.{checkpoint.pk}"
        if checkpoint.status == CheckpointStatus.OPEN:
            checks.append(_check(key, "operations.checkpoints", ReadinessCheckState.SATISFIED, "required_checkpoint_open", f"{checkpoint.label} est ouvert."))
        elif checkpoint.status == CheckpointStatus.PAUSED:
            checks.append(
                _check(
                    key,
                    "operations.checkpoints",
                    ReadinessCheckState.ACTION_REQUIRED,
                    "required_checkpoint_paused",
                    f"Le checkpoint obligatoire « {checkpoint.label} » est en pause.",
                    action=_action("resume_checkpoint", f"Reprendre {checkpoint.label}", "operations.checkpoints"),
                )
            )
        elif checkpoint.status == CheckpointStatus.CLOSED:
            checks.append(
                _check(
                    key,
                    "operations.checkpoints",
                    ReadinessCheckState.BLOCKING,
                    "required_checkpoint_closed",
                    f"Le checkpoint obligatoire « {checkpoint.label} » est fermé.",
                    blocking=True,
                    action=_action("review_checkpoint", f"Configurer un checkpoint exploitable pour {checkpoint.label}", "operations.checkpoints"),
                )
            )
        elif temporal.state == TemporalState.ACTIVE:
            checks.append(
                _check(
                    key,
                    "operations.checkpoints",
                    ReadinessCheckState.BLOCKING,
                    "required_checkpoint_not_open",
                    f"Le checkpoint obligatoire « {checkpoint.label} » n’est pas ouvert pendant l’exécution.",
                    blocking=True,
                    action=_action("open_checkpoint", f"Ouvrir {checkpoint.label}", "operations.checkpoints"),
                )
            )
        else:
            checks.append(
                _check(
                    key,
                    "operations.checkpoints",
                    ReadinessCheckState.WAITING,
                    "required_checkpoint_planned",
                    f"Le checkpoint obligatoire « {checkpoint.label} » est encore planifié.",
                    action=_action("open_checkpoint", f"Ouvrir {checkpoint.label} au moment requis", "operations.checkpoints"),
                )
            )
    return checks


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_assignments_contributor(occurrence, viewer, now):
    temporal = get_temporal_context(occurrence, now=now)
    checkpoints = list(ordered_checkpoints(occurrence=occurrence).filter(required=True, status__in=[CheckpointStatus.OPEN, CheckpointStatus.PAUSED]))
    if not checkpoints:
        return [_check("operations.assignments", "operations.checkpoint_assignment", ReadinessCheckState.NOT_APPLICABLE, "assignments_not_required_now", "Aucune responsabilité de checkpoint active n’est requise maintenant.")]
    checks = []
    for checkpoint in checkpoints:
        assignments = list(active_checkpoint_assignments(checkpoint=checkpoint))
        if assignments:
            checks.append(_check(f"operations.assignments.{checkpoint.pk}", "operations.checkpoint_assignment", ReadinessCheckState.SATISFIED, "checkpoint_assignment_present", f"{checkpoint.label} possède une responsabilité opérationnelle active."))
            continue
        state = (
            ReadinessCheckState.BLOCKING
            if temporal.state == TemporalState.ACTIVE and checkpoint.status == CheckpointStatus.OPEN
            else ReadinessCheckState.ACTION_REQUIRED
        )
        checks.append(
            _check(
                f"operations.assignments.{checkpoint.pk}",
                "operations.checkpoint_assignment",
                state,
                "required_checkpoint_unassigned",
                f"Aucun opérateur n’est affecté au checkpoint « {checkpoint.label} ».",
                blocking=state == ReadinessCheckState.BLOCKING,
                action=_action("assign_checkpoint_operator", f"Affecter un opérateur à {checkpoint.label}", "operations.checkpoint_assignment"),
            )
        )
    return checks


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_authority_contributor(occurrence, viewer, now):
    temporal = get_temporal_context(occurrence, now=now)
    checkpoints = list(ordered_checkpoints(occurrence=occurrence).filter(required=True, status__in=[CheckpointStatus.OPEN, CheckpointStatus.PAUSED]))
    checkpoint_assignments = [
        (checkpoint, list(active_checkpoint_assignments(checkpoint=checkpoint)))
        for checkpoint in checkpoints
    ]
    assignments = [
        assignment
        for _, assignments_for_checkpoint in checkpoint_assignments
        for assignment in assignments_for_checkpoint
    ]
    if not assignments:
        return [_check("operations.authority", "authorization.mandate", ReadinessCheckState.NOT_APPLICABLE, "authority_assignment_not_applicable", "Aucune affectation active ne nécessite de vérification d’autorité.")]
    invalid = [assignment for assignment in assignments if not user_can_manage_activity_operations(assignment.profile, occurrence.activity)]
    if not invalid:
        return [_check("operations.authority", "authorization.mandate", ReadinessCheckState.SATISFIED, "assigned_operators_authorized", "Les opérateurs affectés disposent d’une autorité Operations effective.")]
    invalid_ids = {assignment.pk for assignment in invalid}
    blocking_open_checkpoint = any(
        checkpoint.status == CheckpointStatus.OPEN
        and assignments_for_checkpoint
        and all(assignment.pk in invalid_ids for assignment in assignments_for_checkpoint)
        for checkpoint, assignments_for_checkpoint in checkpoint_assignments
    )
    state = (
        ReadinessCheckState.BLOCKING
        if temporal.state == TemporalState.ACTIVE and blocking_open_checkpoint
        else ReadinessCheckState.ACTION_REQUIRED
    )
    return [
        _check(
            "operations.authority",
            "authorization.mandate",
            state,
            "assigned_operator_without_effective_authority",
            f"{len(invalid)} opérateur(s) affecté(s) n’ont pas d’autorité Operations effective.",
            blocking=state == ReadinessCheckState.BLOCKING,
            action=_action("restore_operator_authority", "Réaffecter un opérateur autorisé ou restaurer un Mandate valide", "authorization.mandate"),
        )
    ]


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_scanner_contributor(occurrence, viewer, now):
    assignments = list(
        ScannerAssignment.objects.filter(activity=occurrence.activity)
        .filter(occurrence=occurrence)
        .select_related("agent")
    )
    if not assignments:
        return [_check("operations.scanner", "scanner.assignment", ReadinessCheckState.NOT_APPLICABLE, "scanner_not_used", "Aucune affectation Scanner n’est configurée pour cette occurrence.")]
    current = [assignment for assignment in assignments if _scanner_assignment_is_current(assignment, now)]
    if not current:
        return [
            _check(
                "operations.scanner",
                "scanner.assignment",
                ReadinessCheckState.ACTION_REQUIRED,
                "scanner_assignment_unavailable",
                "Aucune affectation Scanner configurée n’est actuellement active.",
                action=_action("review_scanner_assignments", "Vérifier les affectations Scanner", "scanner.assignment"),
            )
        ]
    authorized = [assignment for assignment in current if can(assignment.agent, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=occurrence.activity, at=now)]
    if authorized:
        return [_check("operations.scanner", "scanner.assignment", ReadinessCheckState.SATISFIED, "scanner_assignment_operational", "Une affectation Scanner active dispose de l’autorité Access Scan requise.")]
    temporal = get_temporal_context(occurrence, now=now)
    state = ReadinessCheckState.BLOCKING if temporal.state == TemporalState.ACTIVE else ReadinessCheckState.ACTION_REQUIRED
    return [
        _check(
            "operations.scanner",
            "scanner.assignment",
            state,
            "scanner_assignment_without_effective_authority",
            "Les affectations Scanner actives ne disposent pas de l’autorité Access Scan effective.",
            blocking=state == ReadinessCheckState.BLOCKING,
            action=_action("restore_scanner_authority", "Corriger l’autorité Scanner", "scanner.assignment"),
        )
    ]


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_queue_contributor(occurrence, viewer, now):
    temporal = get_temporal_context(occurrence, now=now)
    queues = list(queues_for_occurrence(occurrence=occurrence))
    if not queues:
        return [_check("operations.queue", "operations.queue", ReadinessCheckState.NOT_APPLICABLE, "queue_not_used", "Aucune Live Queue n’est utilisée pour cette occurrence.")]
    if temporal.state == TemporalState.ENDED or occurrence.status == "completed":
        return [_check("operations.queue", "operations.queue", ReadinessCheckState.SATISFIED, "queue_execution_finished", "Les Live Queues ne nécessitent plus d’action après la fin de l’occurrence.")]
    checks = []
    for queue in queues:
        key = f"operations.queue.{queue.pk}"
        if queue.status == QueueStatus.OPEN:
            checks.append(_check(key, "operations.queue", ReadinessCheckState.SATISFIED, "queue_open", f"La file « {queue.label} » est ouverte."))
        elif queue.status == QueueStatus.PAUSED:
            checks.append(_check(key, "operations.queue", ReadinessCheckState.ACTION_REQUIRED, "queue_paused", f"La file « {queue.label} » est en pause.", action=_action("resume_queue", f"Reprendre {queue.label}", "operations.queue")))
        else:
            stranded = queue.entries.filter(status__in=[QueueEntryStatus.WAITING, QueueEntryStatus.CALLED]).exists()
            state = ReadinessCheckState.BLOCKING if stranded and temporal.state == TemporalState.ACTIVE else ReadinessCheckState.ACTION_REQUIRED
            checks.append(
                _check(
                    key,
                    "operations.queue",
                    state,
                    "queue_closed_with_active_entries" if stranded else "queue_closed",
                    f"La file « {queue.label} » est fermée" + (" alors que des entrées sont encore actives." if stranded else "."),
                    blocking=state == ReadinessCheckState.BLOCKING,
                    action=_action("review_queue", f"Vérifier {queue.label}", "operations.queue"),
                )
            )
    return checks


@registry.register(context=OPERATIONS_READINESS_CONTEXT)
def operational_spatial_contributor(occurrence, viewer, now):
    spatial = get_spatial_context(occurrence)
    if spatial.place is None:
        return [_check("operations.spatial", "m6.spatial", ReadinessCheckState.NOT_APPLICABLE, "spatial_context_not_configured", "Aucun lieu canonique n’est configuré pour cette occurrence.")]
    mobility = get_mobility_context(occurrence, target_arrival=occurrence.start_at, now=now)
    hazards = get_hazards(occurrence=occurrence, mobility=mobility, now=now)
    significant = [hazard for hazard in hazards if hazard.severity in {HazardSeverity.WARNING, HazardSeverity.CRITICAL}]
    if significant:
        return [
            _check(
                "operations.spatial",
                "m6.hazards",
                ReadinessCheckState.ACTION_REQUIRED,
                "spatial_hazard_present",
                significant[0].summary,
                action=_action("review_spatial_conditions", "Adapter l’opération aux conditions spatiales", "m6.hazards"),
            )
        ]
    if mobility.status == "routing_unavailable":
        return [_check("operations.spatial", "m6.mobility", ReadinessCheckState.WAITING, "spatial_data_unavailable", "Les données de mobilité externes sont temporairement indisponibles.")]
    return [_check("operations.spatial", "m6.spatial", ReadinessCheckState.SATISFIED, "spatial_context_available", "Le contexte spatial canonique est disponible.")]


def resolve_operational_readiness(occurrence, *, viewer=None, observed_at=None):
    return resolve_readiness(
        occurrence,
        context=OPERATIONS_READINESS_CONTEXT,
        viewer=viewer,
        observed_at=observed_at,
        status_resolver=_operational_status_for,
        next_action_states=(
            ReadinessCheckState.BLOCKING,
            ReadinessCheckState.ACTION_REQUIRED,
            ReadinessCheckState.WAITING,
        ),
    )
