from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.collaboration_models import JourneyStepKind
from journeys.collaboration_services import complete_step, ensure_case_access, is_beneficiary
from opportunities.models import OpportunityRequirementKind
from payments.models import (
    PaymentEvidenceStatus,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from payments.obligation_services import create_payment_obligation, verify_payment_evidence
from payments.services import complete_sandbox_payment

from .models import (
    ServiceCurrentOutcome,
    ServiceJourneyContext,
    ServiceOutcomeEvent,
    ServiceOutcomeEventType,
    ServiceRequirementAssessment,
    ServiceRequirementAssessmentStatus,
    ServiceRequirementPaymentObligation,
    ServiceRequirementStepLink,
    ServiceSubmission,
    ServiceSubmissionMode,
    ServiceSubmissionStatus,
)


SATISFIED_FINANCIAL_OBLIGATION_STATUSES = {
    PaymentObligationStatus.SATISFIED,
    PaymentObligationStatus.WAIVED,
}

SUBMISSION_TRANSITIONS = {
    ServiceSubmissionStatus.PREPARED: {
        ServiceSubmissionStatus.SUBMITTED,
        ServiceSubmissionStatus.FAILED,
        ServiceSubmissionStatus.WITHDRAWN,
    },
    ServiceSubmissionStatus.SUBMITTED: {
        ServiceSubmissionStatus.ACKNOWLEDGED,
        ServiceSubmissionStatus.FAILED,
        ServiceSubmissionStatus.WITHDRAWN,
    },
    ServiceSubmissionStatus.ACKNOWLEDGED: {ServiceSubmissionStatus.WITHDRAWN},
    ServiceSubmissionStatus.FAILED: set(),
    ServiceSubmissionStatus.WITHDRAWN: set(),
}

OUTCOME_PROJECTION = {
    ServiceOutcomeEventType.SUBMITTED: ServiceCurrentOutcome.SUBMITTED,
    ServiceOutcomeEventType.ACKNOWLEDGED: ServiceCurrentOutcome.ACKNOWLEDGED,
    ServiceOutcomeEventType.UNDER_REVIEW: ServiceCurrentOutcome.UNDER_REVIEW,
    ServiceOutcomeEventType.ACTION_REQUIRED: ServiceCurrentOutcome.ACTION_REQUIRED,
    ServiceOutcomeEventType.INTERVIEW: ServiceCurrentOutcome.INTERVIEW,
    ServiceOutcomeEventType.SUCCESSFUL: ServiceCurrentOutcome.SUCCESSFUL,
    ServiceOutcomeEventType.UNSUCCESSFUL: ServiceCurrentOutcome.UNSUCCESSFUL,
    ServiceOutcomeEventType.WITHDRAWN: ServiceCurrentOutcome.WITHDRAWN,
    ServiceOutcomeEventType.OTHER: ServiceCurrentOutcome.UNKNOWN,
}


def _actor_id(actor):
    return getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None


def _ensure_case_operator(actor, journey):
    if getattr(actor, "is_staff", False):
        return
    ensure_case_access(actor, journey, write=True)


def _ensure_submission_owner_or_operator(actor, journey):
    if is_beneficiary(actor, journey) or getattr(actor, "is_staff", False):
        return
    ensure_case_access(actor, journey, write=True)


def _emit_service_event(*, event_type, source_type, source_id, context, suffix, payload=None):
    body = {"journey_id": str(context.journey_id), "context_id": str(context.pk)}
    body.update(payload or {})
    return emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=f"{source_type}:{source_id}:{suffix}"[:255],
        activity_id=context.journey.activity_id,
        space_id=getattr(context.journey.activity, "space_id", None),
        payload=body,
    )


def _set_assessment_status_from_payment(*, assessment, actor=None):
    links = list(
        ServiceRequirementPaymentObligation.objects.filter(assessment=assessment)
        .select_related("obligation")
        .order_by("created_at", "id")
    )
    if not links:
        return assessment
    satisfied = all(link.obligation.status in SATISFIED_FINANCIAL_OBLIGATION_STATUSES for link in links)
    desired = ServiceRequirementAssessmentStatus.SATISFIED if satisfied else ServiceRequirementAssessmentStatus.ACTION_REQUIRED
    if assessment.status == desired:
        return assessment
    assessment.status = desired
    assessment.note = assessment.note or ("Obligation financière satisfaite." if satisfied else "Obligation financière à satisfaire.")
    assessment.assessed_by = actor if _actor_id(actor) else assessment.assessed_by
    assessment.assessed_at = timezone.now()
    assessment._allow_assessment_transition = True
    assessment.save()
    return assessment


@transaction.atomic
def create_requirement_payment_obligation(
    *,
    assessment,
    actor,
    amount,
    currency,
    processing_mode,
    label=None,
    step=None,
    payee_space=None,
    payee_profile=None,
    external_payee_name="",
    due_at=None,
    source_key,
):
    assessment = (
        ServiceRequirementAssessment.objects.select_for_update(of=("self",))
        .select_related("context__journey__activity", "context__opportunity_revision", "requirement")
        .order_by()
        .get(pk=assessment.pk)
    )
    _ensure_case_operator(actor, assessment.context.journey)
    if assessment.requirement.kind != OpportunityRequirementKind.FINANCIAL:
        raise ValidationError("Seul un Requirement financier peut produire une PaymentObligation.")
    if assessment.context.opportunity_revision_id != assessment.requirement.revision_id:
        raise ValidationError("Le Requirement financier doit appartenir à la révision actuellement pinnée.")
    if step is not None:
        if step.journey_id != assessment.context.journey_id:
            raise ValidationError("La JourneyStep appartient à une autre Journey.")
        if step.kind != JourneyStepKind.PAYMENT:
            raise ValidationError("Une obligation financière liée à une Step exige kind=payment.")
        ServiceRequirementStepLink.objects.get_or_create(
            assessment=assessment,
            journey_step=step,
            defaults={"created_by": actor if _actor_id(actor) else None},
        )
    obligation = create_payment_obligation(
        journey=assessment.context.journey,
        reason=PaymentObligationReason.OPPORTUNITY_REQUIREMENT,
        label=(label or assessment.requirement.title).strip(),
        amount=amount,
        currency=currency,
        processing_mode=processing_mode,
        created_by=actor,
        step=step,
        payee_space=payee_space,
        payee_profile=payee_profile,
        external_payee_name=external_payee_name,
        due_at=due_at,
        source_key=source_key,
    )
    link, _ = ServiceRequirementPaymentObligation.objects.get_or_create(
        assessment=assessment,
        obligation=obligation,
        defaults={"created_by": actor if _actor_id(actor) else None},
    )
    _set_assessment_status_from_payment(assessment=assessment, actor=actor)
    return link


@transaction.atomic
def sync_requirement_payment_assessment(*, obligation, actor=None):
    links = list(
        ServiceRequirementPaymentObligation.objects.select_for_update()
        .filter(obligation=obligation)
        .select_related("assessment", "assessment__context", "obligation")
        .order_by("id")
    )
    for link in links:
        _set_assessment_status_from_payment(assessment=link.assessment, actor=actor)
    return [link.assessment for link in links]


@transaction.atomic
def complete_requirement_sandbox_payment(*, payment, actor):
    payment = complete_sandbox_payment(payment=payment, actor=actor)
    if payment.obligation_id:
        sync_requirement_payment_assessment(obligation=payment.obligation, actor=actor)
    return payment


@transaction.atomic
def verify_requirement_payment_evidence(*, evidence, actor, review_note=""):
    evidence = verify_payment_evidence(evidence=evidence, actor=actor, review_note=review_note)
    sync_requirement_payment_assessment(obligation=evidence.obligation, actor=actor)
    return evidence


def validate_payment_step_completion(step):
    obligations = step.payment_obligations.all()
    blocking = obligations.exclude(status__in=SATISFIED_FINANCIAL_OBLIGATION_STATUSES).first()
    if blocking is not None:
        raise ValidationError("Cette étape de paiement conserve une PaymentObligation non satisfaite.")
    return True


@transaction.atomic
def complete_service_step(*, step, actor, reason="completed"):
    if step.kind == JourneyStepKind.PAYMENT:
        validate_payment_step_completion(step)
    return complete_step(step=step, actor=actor, reason=reason)


@transaction.atomic
def prepare_service_submission(*, context, actor, mode, receipt_artifact=None, external_reference=""):
    context = (
        ServiceJourneyContext.objects.select_for_update(of=("self",))
        .select_related("journey__activity")
        .order_by()
        .get(pk=context.pk)
    )
    _ensure_submission_owner_or_operator(actor, context.journey)
    if mode not in ServiceSubmissionMode.values:
        raise ValidationError("Mode de soumission inconnu.")
    if receipt_artifact is not None and receipt_artifact.journey_id != context.journey_id:
        raise PermissionDenied("Le reçu de soumission appartient à une autre Journey.")
    attempt = (ServiceSubmission.objects.filter(context=context).aggregate(value=Max("attempt"))["value"] or 0) + 1
    submission = ServiceSubmission(
        context=context,
        attempt=attempt,
        mode=mode,
        receipt_artifact=receipt_artifact,
        external_reference=(external_reference or "").strip(),
        submitted_by=actor if _actor_id(actor) else None,
    )
    try:
        submission.save()
    except IntegrityError as exc:
        raise ValidationError("Impossible de réserver un numéro de tentative unique.") from exc
    return submission


def _lock_submission(submission):
    return (
        ServiceSubmission.objects.select_for_update(of=("self",))
        .select_related("context__journey__activity", "receipt_artifact")
        .order_by()
        .get(pk=submission.pk)
    )


def _project_current_outcome(context):
    event = (
        ServiceOutcomeEvent.objects.filter(context=context)
        .order_by("-occurred_at", "-created_at", "-id")
        .first()
    )
    return OUTCOME_PROJECTION.get(event.event_type, ServiceCurrentOutcome.UNKNOWN) if event else ServiceCurrentOutcome.NOT_SUBMITTED


def _record_service_outcome(*, context, actor, event_type, occurred_at, note="", external_reference="", require_operator):
    context = (
        ServiceJourneyContext.objects.select_for_update(of=("self",))
        .select_related("journey__activity")
        .order_by()
        .get(pk=context.pk)
    )
    if require_operator:
        _ensure_case_operator(actor, context.journey)
    if event_type not in ServiceOutcomeEventType.values:
        raise ValidationError("Type de résultat externe inconnu.")
    if occurred_at is None:
        raise ValidationError("occurred_at est obligatoire pour un résultat externe.")
    event = ServiceOutcomeEvent.objects.create(
        context=context,
        event_type=event_type,
        occurred_at=occurred_at,
        recorded_by=actor if _actor_id(actor) else None,
        note=note or "",
        external_reference=(external_reference or "").strip(),
    )
    projected = _project_current_outcome(context)
    changed = projected != context.current_outcome
    if changed:
        context.current_outcome = projected
        context._allow_outcome_projection = True
        context.save(update_fields=["current_outcome", "updated_at"])
    _emit_service_event(
        event_type=DomainEventType.SERVICE_OUTCOME_CHANGED,
        source_type="service_outcome_event",
        source_id=event.pk,
        context=context,
        suffix="recorded",
        payload={"event_type": event.event_type, "current_outcome": projected, "projection_changed": changed},
    )
    return event


def _transition_submission(*, submission, actor, status, failure_reason="", external_reference=None, receipt_artifact=None):
    expected_status = submission.status
    submission = _lock_submission(submission)
    _ensure_submission_owner_or_operator(actor, submission.context.journey)
    if status == submission.status:
        return submission
    if submission.status != expected_status:
        raise ValidationError("La ServiceSubmission a changé d’état pendant cette transition. Rechargez-la avant de réessayer.")
    if status not in SUBMISSION_TRANSITIONS.get(submission.status, set()):
        raise ValidationError(f"Transition ServiceSubmission interdite: {submission.status} -> {status}.")
    if receipt_artifact is not None:
        if receipt_artifact.journey_id != submission.context.journey_id:
            raise PermissionDenied("Le reçu de soumission appartient à une autre Journey.")
        submission.receipt_artifact = receipt_artifact
    if external_reference is not None:
        submission.external_reference = (external_reference or "").strip()
    now = timezone.now()
    submission.status = status
    if status in {ServiceSubmissionStatus.SUBMITTED, ServiceSubmissionStatus.ACKNOWLEDGED} and submission.submitted_at is None:
        submission.submitted_at = now
    if status == ServiceSubmissionStatus.FAILED:
        submission.failure_reason = (failure_reason or "")[:2000]
    submission._allow_status_transition = True
    submission.save()
    event_type = {
        ServiceSubmissionStatus.SUBMITTED: DomainEventType.SERVICE_SUBMISSION_SUBMITTED,
        ServiceSubmissionStatus.ACKNOWLEDGED: DomainEventType.SERVICE_SUBMISSION_ACKNOWLEDGED,
        ServiceSubmissionStatus.FAILED: DomainEventType.SERVICE_SUBMISSION_FAILED,
        ServiceSubmissionStatus.WITHDRAWN: DomainEventType.SERVICE_SUBMISSION_WITHDRAWN,
    }.get(status)
    if event_type:
        _emit_service_event(
            event_type=event_type,
            source_type="service_submission",
            source_id=submission.pk,
            context=submission.context,
            suffix=status,
            payload={"attempt": submission.attempt, "status": submission.status, "mode": submission.mode},
        )
    if status in {ServiceSubmissionStatus.SUBMITTED, ServiceSubmissionStatus.ACKNOWLEDGED}:
        _record_service_outcome(
            context=submission.context,
            actor=actor,
            event_type=ServiceOutcomeEventType.SUBMITTED if status == ServiceSubmissionStatus.SUBMITTED else ServiceOutcomeEventType.ACKNOWLEDGED,
            occurred_at=submission.submitted_at or now,
            external_reference=submission.external_reference,
            note=f"ServiceSubmission attempt {submission.attempt}",
            require_operator=False,
        )
    elif status == ServiceSubmissionStatus.WITHDRAWN:
        _record_service_outcome(
            context=submission.context,
            actor=actor,
            event_type=ServiceOutcomeEventType.WITHDRAWN,
            occurred_at=now,
            external_reference=submission.external_reference,
            note=f"ServiceSubmission attempt {submission.attempt} withdrawn",
            require_operator=False,
        )
    return submission


@transaction.atomic
def submit_service_submission(*, submission, actor, external_reference=None, receipt_artifact=None):
    return _transition_submission(
        submission=submission,
        actor=actor,
        status=ServiceSubmissionStatus.SUBMITTED,
        external_reference=external_reference,
        receipt_artifact=receipt_artifact,
    )


@transaction.atomic
def acknowledge_service_submission(*, submission, actor, external_reference=None):
    submission = _lock_submission(submission)
    _ensure_case_operator(actor, submission.context.journey)
    return _transition_submission(
        submission=submission,
        actor=actor,
        status=ServiceSubmissionStatus.ACKNOWLEDGED,
        external_reference=external_reference,
    )


@transaction.atomic
def fail_service_submission(*, submission, actor, failure_reason):
    return _transition_submission(
        submission=submission,
        actor=actor,
        status=ServiceSubmissionStatus.FAILED,
        failure_reason=failure_reason,
    )


@transaction.atomic
def withdraw_service_submission(*, submission, actor):
    return _transition_submission(submission=submission, actor=actor, status=ServiceSubmissionStatus.WITHDRAWN)


@transaction.atomic
def record_service_outcome(*, context, actor, event_type, occurred_at, note="", external_reference=""):
    return _record_service_outcome(
        context=context,
        actor=actor,
        event_type=event_type,
        occurred_at=occurred_at,
        note=note,
        external_reference=external_reference,
        require_operator=True,
    )
