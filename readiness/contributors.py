from access.models import AccessStatus
from activities.models import OccurrenceStatus
from capacity.models import CapacityReservationStatus
from journeys.collaboration_models import (
    JourneyAssignmentStatus,
    JourneyBlockerStatus,
    JourneyStepStatus,
    TERMINAL_STEP_STATUSES,
)
from journeys.models import JourneyStatus, RequestStatus, WorkflowKind
from payments.models import PaymentObligationStatus
from requirements.contracts import RequirementAssessmentState

from .registry import registry
from .types import NextAction, ReadinessCheck, ReadinessCheckState


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


@registry.register
def journey_contributor(journey, viewer, now):
    status = journey.status
    if status == JourneyStatus.DRAFT:
        action = NextAction("continue_journey", "Continuer la démarche", source="journey")
        return [_check("journey.status", "journey", ReadinessCheckState.ACTION_REQUIRED, "journey_draft", "La démarche doit être complétée.", action=action)]
    if status == JourneyStatus.PENDING_APPROVAL:
        return [_check("journey.status", "journey", ReadinessCheckState.WAITING, "request_pending", "La démarche attend une validation.")]
    if status == JourneyStatus.PENDING_PAYMENT and not list(journey.payment_obligations.all()):
        action = NextAction("pay", "Payer", source="journey")
        return [_check("journey.status", "journey", ReadinessCheckState.ACTION_REQUIRED, "payment_required", "Un paiement est requis.", action=action)]
    if status == JourneyStatus.SUBMITTED:
        if journey.workflow == WorkflowKind.INVITATION:
            action = NextAction("respond_invitation", "Répondre à l’invitation", source="journey")
            return [_check("journey.status", "journey", ReadinessCheckState.ACTION_REQUIRED, "participant_response_required", "Votre réponse est attendue.", action=action)]
        return [_check("journey.status", "journey", ReadinessCheckState.WAITING, "journey_submitted", "La démarche a été envoyée et suit son traitement.")]
    if status in {JourneyStatus.REJECTED, JourneyStatus.CANCELLED, JourneyStatus.EXPIRED}:
        reason = {
            JourneyStatus.REJECTED: "request_rejected",
            JourneyStatus.CANCELLED: "journey_cancelled",
            JourneyStatus.EXPIRED: "journey_expired",
        }[status]
        summary = {
            JourneyStatus.REJECTED: "La démarche a été refusée.",
            JourneyStatus.CANCELLED: "La démarche a été annulée.",
            JourneyStatus.EXPIRED: "La démarche a expiré.",
        }[status]
        return [_check("journey.status", "journey", ReadinessCheckState.BLOCKING, reason, summary, blocking=True)]
    return [_check("journey.status", "journey", ReadinessCheckState.SATISFIED, "journey_progressing", "L’état de la démarche permet de continuer.")]


@registry.register
def request_contributor(journey, viewer, now):
    rows = list(journey.requests.all())
    if not rows:
        return [_check("journey.request", "journey_request", ReadinessCheckState.NOT_APPLICABLE, "request_not_applicable", "Aucune demande distincte n’est requise.")]
    current = rows[0]
    if current.status == RequestStatus.PENDING:
        return [_check("journey.request", "journey_request", ReadinessCheckState.WAITING, "request_pending", "Une demande attend une décision.")]
    if current.status == RequestStatus.REJECTED:
        return [_check("journey.request", "journey_request", ReadinessCheckState.BLOCKING, "request_rejected", "La demande requise a été refusée.", blocking=True)]
    if current.status == RequestStatus.APPROVED:
        return [_check("journey.request", "journey_request", ReadinessCheckState.SATISFIED, "request_approved", "La demande requise est approuvée.")]
    return [_check("journey.request", "journey_request", ReadinessCheckState.NOT_APPLICABLE, "request_closed", "La demande n’exige plus d’action de préparation.")]


@registry.register
def steps_contributor(journey, viewer, now):
    checks = []
    beneficiary_id = journey.beneficiary_id
    for step in journey.steps.all():
        if not step.is_required or step.status in TERMINAL_STEP_STATUSES:
            continue
        key = f"journey.step.{step.pk}"
        if step.status == JourneyStepStatus.BLOCKED:
            checks.append(_check(key, "journey_step", ReadinessCheckState.BLOCKING, "journey_step_blocked", step.title, blocking=True))
            continue
        dependencies = [dependency.depends_on for dependency in step.dependencies.all()]
        if any(dependency.status not in TERMINAL_STEP_STATUSES for dependency in dependencies):
            checks.append(_check(key, "journey_step", ReadinessCheckState.WAITING, "participant_step_dependency_waiting", step.title))
            continue
        assignments = [assignment for assignment in step.assignments.all() if assignment.status == JourneyAssignmentStatus.ACTIVE]
        participant_assigned = any(assignment.profile_id == beneficiary_id for assignment in assignments)
        if participant_assigned or (not assignments and step.created_by_id == beneficiary_id):
            action = NextAction("complete_step", step.title, source="journey_step")
            checks.append(_check(key, "journey_step", ReadinessCheckState.ACTION_REQUIRED, "participant_step_required", step.title, action=action))
        else:
            checks.append(_check(key, "journey_step", ReadinessCheckState.WAITING, "operator_step_pending", step.title))
    if not checks:
        checks.append(_check("journey.steps", "journey_step", ReadinessCheckState.NOT_APPLICABLE, "steps_satisfied_or_not_applicable", "Aucune étape obligatoire en attente."))
    return checks


@registry.register
def blockers_contributor(journey, viewer, now):
    active = [blocker for blocker in journey.blockers.all() if blocker.status == JourneyBlockerStatus.ACTIVE]
    if not active:
        return [_check("journey.blockers", "journey_blocker", ReadinessCheckState.SATISFIED, "no_active_blocker", "Aucun obstacle actif.")]
    return [
        _check(f"journey.blocker.{blocker.pk}", "journey_blocker", ReadinessCheckState.BLOCKING, "journey_blocker_active", blocker.title, blocking=True)
        for blocker in active
    ]


@registry.register
def payments_contributor(journey, viewer, now):
    obligations = list(journey.payment_obligations.all())
    if not obligations:
        return [_check("payments", "payment_obligation", ReadinessCheckState.NOT_APPLICABLE, "payment_not_applicable", "Aucune obligation de paiement n’est requise.")]
    checks = []
    for obligation in obligations:
        key = f"payment_obligation.{obligation.pk}"
        if obligation.status in {PaymentObligationStatus.SATISFIED, PaymentObligationStatus.WAIVED}:
            checks.append(_check(key, "payment_obligation", ReadinessCheckState.SATISFIED, "payment_satisfied", obligation.label))
        elif obligation.status == PaymentObligationStatus.PROCESSING:
            checks.append(_check(key, "payment_obligation", ReadinessCheckState.WAITING, "payment_pending", obligation.label))
        elif obligation.status == PaymentObligationStatus.PENDING:
            if obligation.payer_profile_id == journey.beneficiary_id or (obligation.payer_profile_id is None and obligation.payer_space_id is None):
                action = NextAction("pay", "Payer", source="payment_obligation")
                checks.append(_check(key, "payment_obligation", ReadinessCheckState.ACTION_REQUIRED, "payment_required", obligation.label, action=action))
            else:
                checks.append(_check(key, "payment_obligation", ReadinessCheckState.WAITING, "payment_waiting_on_payer", obligation.label))
        else:
            checks.append(_check(key, "payment_obligation", ReadinessCheckState.BLOCKING, "payment_unavailable", obligation.label, blocking=True))
    return checks


@registry.register
def capacity_contributor(journey, viewer, now):
    reservations = list(journey.capacity_reservations.all())
    if not reservations:
        return [_check("capacity", "capacity", ReadinessCheckState.NOT_APPLICABLE, "capacity_not_applicable", "Aucune réservation de capacité n’est requise.")]
    active = [reservation for reservation in reservations if reservation.status in {CapacityReservationStatus.HELD, CapacityReservationStatus.COMMITTED} and (reservation.status != CapacityReservationStatus.HELD or reservation.expires_at is None or reservation.expires_at > now)]
    if active:
        return [_check("capacity", "capacity", ReadinessCheckState.SATISFIED, "capacity_secured", "La capacité nécessaire est sécurisée.")]
    return [_check("capacity", "capacity", ReadinessCheckState.BLOCKING, "capacity_not_secured", "La capacité nécessaire n’est plus sécurisée.", blocking=True)]


@registry.register
def access_contributor(journey, viewer, now):
    accesses = list(journey.accesses.all())
    if not accesses:
        return [_check("access", "access", ReadinessCheckState.NOT_APPLICABLE, "access_not_applicable", "Aucun droit d’accès distinct n’est requis par ce contexte.")]
    if any(access.status in {AccessStatus.VALID, AccessStatus.USED} for access in accesses):
        return [_check("access", "access", ReadinessCheckState.SATISFIED, "access_available", "Le droit d’accès est disponible.")]
    if any(access.status == AccessStatus.PENDING for access in accesses):
        return [_check("access", "access", ReadinessCheckState.WAITING, "access_pending", "Le droit d’accès est en préparation.")]
    return [_check("access", "access", ReadinessCheckState.BLOCKING, "access_unavailable", "Le droit d’accès requis n’est pas disponible.", blocking=True)]


@registry.register
def occurrence_contributor(journey, viewer, now):
    occurrence = journey.occurrence
    if occurrence is None:
        return [_check("occurrence", "occurrence", ReadinessCheckState.NOT_APPLICABLE, "occurrence_not_applicable", "Cette démarche ne dépend pas d’une occurrence physique.")]
    if occurrence.status == OccurrenceStatus.CANCELLED:
        return [_check("occurrence", "occurrence", ReadinessCheckState.BLOCKING, "occurrence_cancelled", "L’occurrence a été annulée.", blocking=True)]
    return [_check("occurrence", "occurrence", ReadinessCheckState.SATISFIED, "occurrence_available", "L’occurrence est exploitable.")]


@registry.register
def service_requirements_contributor(journey, viewer, now):
    context = getattr(journey, "service_context", None)
    if context is None:
        return [_check("requirements", "requirements", ReadinessCheckState.NOT_APPLICABLE, "requirements_not_applicable", "Aucune évaluation Services n’est applicable.")]
    checks = []
    for assessment in context.requirement_assessments.all():
        requirement = assessment.requirement
        if not requirement.is_mandatory:
            continue
        key = f"requirement.{assessment.pk}"
        if assessment.status == RequirementAssessmentState.SATISFIED:
            checks.append(_check(key, "requirements", ReadinessCheckState.SATISFIED, "requirement_satisfied", requirement.title))
        elif assessment.status == RequirementAssessmentState.NOT_APPLICABLE:
            checks.append(_check(key, "requirements", ReadinessCheckState.NOT_APPLICABLE, "requirement_not_applicable", requirement.title))
        elif assessment.status == RequirementAssessmentState.PENDING:
            checks.append(_check(key, "requirements", ReadinessCheckState.WAITING, "requirement_pending", requirement.title))
        elif assessment.status == RequirementAssessmentState.UNASSESSED:
            checks.append(_check(key, "requirements", ReadinessCheckState.WAITING, "requirement_unassessed", requirement.title))
        else:
            checks.append(_check(key, "requirements", ReadinessCheckState.BLOCKING, "requirement_unsatisfied", requirement.title, blocking=True))
    if not checks:
        checks.append(_check("requirements", "requirements", ReadinessCheckState.NOT_APPLICABLE, "requirements_satisfied_or_not_applicable", "Aucun Requirement obligatoire en attente."))
    return checks
