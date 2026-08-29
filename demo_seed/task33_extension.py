from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyStep,
    JourneyStepKind,
    JourneyStepOrigin,
    JourneyStepStatus,
)
from journeys.collaboration_services import create_artifact
from journeys.models import Journey, JourneyStatus, WorkflowKind
from opportunities.models import Opportunity, OpportunityRequirementKind
from payments.models import (
    Payment,
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentMethod,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationStatus,
    PaymentStatus,
)
from payments.obligation_services import (
    create_commerce_payment_obligation,
    submit_payment_evidence,
    satisfy_payment_obligation,
)
from payments.services import initiate_obligation_payment
from requirements.contracts import RequirementAssessmentState
from services.models import (
    CompletionPolicy,
    OpportunityPolicy,
    ServiceCurrentOutcome,
    ServiceDetails,
    ServiceJourneyContext,
    ServiceKind,
    ServiceOutcomeEvent,
    ServiceOutcomeEventType,
    ServiceRequirementAssessment,
    ServiceRequirementStepLink,
    ServiceSubmission,
    ServiceSubmissionMode,
    ServiceSubmissionStatus,
)
from services.t33_services import (
    complete_requirement_sandbox_payment,
    create_requirement_payment_obligation,
    prepare_service_submission,
    record_service_outcome,
    submit_service_submission,
    verify_requirement_payment_evidence,
)

from .common import SeedContext, stable_uuid


def _service_activity(*, staff):
    activity, _ = Activity.objects.get_or_create(
        pk=stable_uuid("task33-service-activity"),
        defaults={
            "owner_profile": staff,
            "created_by": staff,
            "title": "Accompagnement candidatures — bêta T33",
            "slug": "beta-t33-services",
            "short_description": "Scénarios financiers et résultats externes T33.",
            "description": "Activity Services fictive réservée à la validation bêta Makolo.",
            "status": ActivityStatus.PUBLISHED,
            "visibility": ActivityVisibility.PRIVATE,
        },
    )
    ServiceDetails.objects.update_or_create(
        activity=activity,
        defaults={
            "service_kind": ServiceKind.APPLICATION_SUPPORT,
            "opportunity_policy": OpportunityPolicy.REQUIRED,
            "allows_external_beneficiary": False,
            "completion_policy": CompletionPolicy.REQUIRED_STEPS_AND_SUBMISSION,
        },
    )
    return activity


def _journey_context(*, key, activity, participant, opportunity, revision, status=JourneyStatus.IN_PROGRESS, fulfilled_at=None):
    journey, _ = Journey.objects.get_or_create(
        pk=stable_uuid(f"task33-service-journey:{key}"),
        defaults={
            "initiated_by": participant,
            "beneficiary": participant,
            "activity": activity,
            "workflow": WorkflowKind.SERVICE,
            "status": status,
            "submitted_at": fulfilled_at,
            "confirmed_at": fulfilled_at,
            "started_at": fulfilled_at,
            "fulfilled_at": fulfilled_at if status == JourneyStatus.FULFILLED else None,
        },
    )
    context, _ = ServiceJourneyContext.objects.get_or_create(
        pk=stable_uuid(f"task33-service-context:{key}"),
        defaults={
            "journey": journey,
            "opportunity": opportunity,
            "opportunity_revision": revision,
            "objective": f"Scénario bêta T33 — {key}",
            "current_outcome": ServiceCurrentOutcome.NOT_SUBMITTED,
        },
    )
    return journey, context


def _financial_assessment(*, key, context, requirement, staff):
    assessment, _ = ServiceRequirementAssessment.objects.get_or_create(
        pk=stable_uuid(f"task33-financial-assessment:{key}"),
        defaults={
            "context": context,
            "requirement": requirement,
            "status": RequirementAssessmentState.UNASSESSED,
        },
    )
    step, _ = JourneyStep.objects.get_or_create(
        pk=stable_uuid(f"task33-payment-step:{key}"),
        defaults={
            "journey": context.journey,
            "kind": JourneyStepKind.PAYMENT,
            "title": "Payer les frais de candidature",
            "description": "Condition financière fictive de l’Opportunity bêta.",
            "status": JourneyStepStatus.IN_PROGRESS,
            "position": 10,
            "is_required": True,
            "origin": JourneyStepOrigin.MANUAL,
            "started_at": context.journey.started_at,
            "created_by": staff,
            "status_changed_by": staff,
            "status_reason": "beta_t33_financial_requirement",
        },
    )
    ServiceRequirementStepLink.objects.get_or_create(
        assessment=assessment,
        journey_step=step,
        defaults={"created_by": staff},
    )
    return assessment, step


def _pdf_upload(name: str, body: bytes):
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n" + body + b"\n%%EOF",
        content_type="application/pdf",
    )


def _artifact(*, journey, step, participant, kind, title, filename, body):
    existing = JourneyArtifact.objects.filter(
        journey=journey,
        step=step,
        kind=kind,
        title=title,
        version=1,
    ).first()
    if existing:
        return existing
    return create_artifact(
        journey=journey,
        step=step,
        uploaded_file=_pdf_upload(filename, body),
        uploaded_by=participant,
        kind=kind,
        title=title,
    )


def _attach_commerce_obligations(*, staff):
    payments = list(
        Payment.objects.filter(
            metadata__seed="makolo-beta",
            status=PaymentStatus.SUCCEEDED,
            commerce_order__isnull=False,
        ).select_related(
            "commerce_order__journey__activity__space",
            "commerce_order__journey__activity__owner_profile",
            "obligation",
        )
    )
    for payment in payments:
        obligation = payment.obligation
        if obligation is None:
            obligation = create_commerce_payment_obligation(
                commerce_order=payment.commerce_order,
                actor=staff,
            )
            Payment.objects.filter(pk=payment.pk).update(obligation=obligation)
        if obligation.status != PaymentObligationStatus.SATISFIED:
            satisfy_payment_obligation(
                obligation=obligation,
                source=f"beta-seed-payment:{payment.pk}",
            )
    return len(payments)


def seed_task33_extension(ctx: SeedContext, *, users: dict[str, object]) -> None:
    staff = users["staff"]
    participant = users["participant"]
    commerce_count = _attach_commerce_obligations(staff=staff)

    opportunity = Opportunity.objects.get(pk=stable_uuid("task32-opportunity:scholarship"))
    opportunity.refresh_from_db()
    revision = opportunity.current_revision
    requirement = revision.requirements.get(kind=OpportunityRequirementKind.FINANCIAL)
    activity = _service_activity(staff=staff)

    sandbox_journey, sandbox_context = _journey_context(
        key="sandbox-fee",
        activity=activity,
        participant=participant,
        opportunity=opportunity,
        revision=revision,
    )
    sandbox_assessment, sandbox_step = _financial_assessment(
        key="sandbox-fee",
        context=sandbox_context,
        requirement=requirement,
        staff=staff,
    )
    sandbox_link = create_requirement_payment_obligation(
        assessment=sandbox_assessment,
        actor=staff,
        step=sandbox_step,
        amount=Decimal("50.00"),
        currency="USD",
        processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
        external_payee_name="Université Démo T33",
        source_key="beta:t33:opportunity-fee:sandbox",
    )
    with override_settings(PAYMENTS_SANDBOX_ENABLED=True):
        sandbox_payment = initiate_obligation_payment(
            obligation=sandbox_link.obligation,
            actor=participant,
            provider="sandbox",
            method=PaymentMethod.MOBILE_MONEY,
            idempotency_key="beta:t33:opportunity-fee:sandbox:payment",
        )
        complete_requirement_sandbox_payment(payment=sandbox_payment, actor=participant)

    external_journey, external_context = _journey_context(
        key="external-fee",
        activity=activity,
        participant=participant,
        opportunity=opportunity,
        revision=revision,
    )
    external_assessment, external_step = _financial_assessment(
        key="external-fee",
        context=external_context,
        requirement=requirement,
        staff=staff,
    )
    external_link = create_requirement_payment_obligation(
        assessment=external_assessment,
        actor=staff,
        step=external_step,
        amount=Decimal("50.00"),
        currency="USD",
        processing_mode=PaymentObligationProcessingMode.EXTERNAL,
        external_payee_name="Université Démo T33",
        source_key="beta:t33:opportunity-fee:external",
    )
    receipt = _artifact(
        journey=external_journey,
        step=external_step,
        participant=participant,
        kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        title="Reçu externe bêta T33",
        filename="beta-t33-payment-receipt.pdf",
        body=b"Makolo beta T33 external payment receipt",
    )
    evidence = PaymentEvidence.objects.filter(
        obligation=external_link.obligation,
        artifact=receipt,
    ).first()
    if evidence is None:
        evidence = submit_payment_evidence(
            obligation=external_link.obligation,
            artifact=receipt,
            actor=participant,
            paid_at=ctx.as_of,
            external_reference="BETA-T33-EXT-FEE",
        )
    if evidence.status != PaymentEvidenceStatus.VERIFIED:
        verify_requirement_payment_evidence(
            evidence=evidence,
            actor=staff,
            review_note="Preuve externe fictive vérifiée pour la bêta T33.",
        )

    submission_journey, submission_context = _journey_context(
        key="submission-outcome",
        activity=activity,
        participant=participant,
        opportunity=opportunity,
        revision=revision,
        status=JourneyStatus.FULFILLED,
        fulfilled_at=ctx.as_of,
    )
    submission_receipt = _artifact(
        journey=submission_journey,
        step=None,
        participant=participant,
        kind=JourneyArtifactKind.OTHER,
        title="Accusé de soumission bêta T33",
        filename="beta-t33-submission-receipt.pdf",
        body=b"Makolo beta T33 submission receipt",
    )
    submission = ServiceSubmission.objects.filter(context=submission_context, attempt=1).first()
    if submission is None:
        submission = prepare_service_submission(
            context=submission_context,
            actor=participant,
            mode=ServiceSubmissionMode.EXTERNAL_WEB,
            receipt_artifact=submission_receipt,
        )
    if submission.status == ServiceSubmissionStatus.PREPARED:
        submission = submit_service_submission(
            submission=submission,
            actor=participant,
            external_reference="BETA-T33-APPLICATION-001",
        )
    if not ServiceOutcomeEvent.objects.filter(
        context=submission_context,
        event_type=ServiceOutcomeEventType.UNSUCCESSFUL,
        external_reference="BETA-T33-OUTCOME-001",
    ).exists():
        record_service_outcome(
            context=submission_context,
            actor=staff,
            event_type=ServiceOutcomeEventType.UNSUCCESSFUL,
            occurred_at=(submission.submitted_at or ctx.as_of) + timedelta(hours=1),
            external_reference="BETA-T33-OUTCOME-001",
            note="Décision externe fictive : candidature non retenue.",
        )

    ctx.add("beta_t33_commerce_obligations", commerce_count)
    ctx.add("beta_t33_sandbox_obligations", PaymentObligation.objects.filter(source_key="beta:t33:opportunity-fee:sandbox").count())
    ctx.add("beta_t33_external_obligations", PaymentObligation.objects.filter(source_key="beta:t33:opportunity-fee:external").count())
    ctx.add("beta_t33_payment_evidence", PaymentEvidence.objects.filter(obligation=external_link.obligation).count())
    ctx.add("beta_t33_submissions", ServiceSubmission.objects.filter(context=submission_context).count())
    ctx.add("beta_t33_outcomes", ServiceOutcomeEvent.objects.filter(context=submission_context).count())
