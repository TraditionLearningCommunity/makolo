from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from activities.models import Activity
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility, JourneyStepKind
from journeys.collaboration_services import assign_journey, create_artifact, start_step
from journeys.models import JourneyStatus
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import add_requirement, create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision
from payments.models import Payment, PaymentObligationProcessingMode, PaymentObligationStatus, PaymentProvider
from payments.obligation_services import submit_payment_evidence
from payments.services import initiate_obligation_payment

from .models import (
    CompletionPolicy,
    OpportunityPolicy,
    ServiceCurrentOutcome,
    ServiceKind,
    ServiceOutcomeEventType,
    ServiceRequirementAssessmentStatus,
    ServiceSubmissionMode,
    ServiceSubmissionStatus,
)
from .requirement_services import create_requirement_step
from .services import (
    add_template_step,
    create_plan_template,
    create_service_details,
    create_service_journey,
    fulfill_service_journey,
    publish_plan_template,
    start_service_journey,
    submit_service_journey,
)
from .t33_services import (
    acknowledge_service_submission,
    complete_requirement_sandbox_payment,
    complete_service_step,
    create_requirement_payment_obligation,
    prepare_service_submission,
    record_service_outcome,
    submit_service_submission,
    verify_requirement_payment_evidence,
)


User = get_user_model()


def pdf_upload(name="receipt.pdf", text=b"T33 receipt"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class ServiceT33FinancialRequirementTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="t33-curator", email="t33-curator@example.com", password="x", is_staff=True, is_superuser=True)
        self.manager = User.objects.create_user(username="t33-service-manager", email="t33-service-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t33-service-beneficiary", email="t33-service-beneficiary@example.com", password="x")
        self.outsider = User.objects.create_user(username="t33-service-outsider", email="t33-service-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Bourse T33")
        grant_activity_role(profile=self.manager, activity=self.activity)
        self.service = create_service_details(
            activity=self.activity,
            actor=self.manager,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        template = create_plan_template(service=self.service, actor=self.manager, key="scholarship", name="Candidature bourse")
        add_template_step(template=template, actor=self.manager, title="Préparer dossier", position=10)
        self.template = publish_plan_template(template=template, actor=self.manager)
        self.opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.SCHOLARSHIP)
        revision = create_opportunity_revision(
            opportunity=self.opportunity,
            actor=self.curator,
            title="Bourse externe T33",
            issuer_name="Université X",
            summary="Bourse avec frais de candidature",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=self.opportunity,
            actor=self.curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Site officiel",
            url=f"https://example.test/t33/{self.opportunity.pk}",
            is_primary=True,
            verified=True,
        )
        add_requirement(revision=revision, actor=self.curator, kind=OpportunityRequirementKind.FINANCIAL, title="Frais de candidature", position=10)
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision, actor=self.curator)
        self.journey = create_service_journey(
            service=self.service,
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            template=self.template,
            opportunity=self.opportunity,
        )
        assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        confirmed = submit_service_journey(journey=self.journey, actor=self.beneficiary)
        self.journey = start_service_journey(journey=confirmed, actor=self.manager)
        self.assessment = self.journey.service_context.requirement_assessments.get()
        self.step_link = create_requirement_step(assessment=self.assessment, actor=self.manager, title="Payer les frais")
        self.payment_step = self.step_link.journey_step

    def test_sandbox_financial_requirement_satisfies_assessment_without_global_pending_payment(self):
        link = create_requirement_payment_obligation(
            assessment=self.assessment,
            actor=self.manager,
            step=self.payment_step,
            amount=Decimal("50.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            external_payee_name="Université X",
            source_key="t33:scholarship:sandbox",
        )
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, ServiceRequirementAssessmentStatus.ACTION_REQUIRED)
        start_step(step=self.payment_step, actor=self.manager)
        with self.assertRaises(ValidationError):
            complete_service_step(step=self.payment_step, actor=self.manager)
        payment = initiate_obligation_payment(
            obligation=link.obligation,
            actor=self.beneficiary,
            provider=PaymentProvider.SANDBOX,
            method="mobile_money",
            idempotency_key="t33-scholarship-attempt",
        )
        complete_requirement_sandbox_payment(payment=payment, actor=self.beneficiary)
        link.obligation.refresh_from_db()
        self.assessment.refresh_from_db()
        self.journey.refresh_from_db()
        self.assertEqual(link.obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertEqual(self.assessment.status, ServiceRequirementAssessmentStatus.SATISFIED)
        self.assertEqual(self.journey.status, JourneyStatus.IN_PROGRESS)
        complete_service_step(step=self.payment_step, actor=self.manager)

    def test_external_fee_uses_artifact_evidence_and_creates_no_payment(self):
        link = create_requirement_payment_obligation(
            assessment=self.assessment,
            actor=self.manager,
            step=self.payment_step,
            amount=Decimal("50.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            external_payee_name="Université X",
            source_key="t33:scholarship:external",
        )
        artifact = create_artifact(
            journey=self.journey,
            step=self.payment_step,
            uploaded_file=pdf_upload(),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.PAYMENT_RECEIPT,
            title="Reçu frais candidature",
        )
        before = Payment.objects.count()
        evidence = submit_payment_evidence(obligation=link.obligation, artifact=artifact, actor=self.beneficiary, paid_at=timezone.now(), external_reference="UNI-EXT-50")
        verify_requirement_payment_evidence(evidence=evidence, actor=self.manager, review_note="Reçu validé")
        self.assessment.refresh_from_db()
        link.obligation.refresh_from_db()
        self.assertEqual(Payment.objects.count(), before)
        self.assertEqual(link.obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertEqual(self.assessment.status, ServiceRequirementAssessmentStatus.SATISFIED)

    def test_foreign_step_and_outsider_cannot_create_financial_obligation(self):
        other_activity = Activity.objects.create(owner_profile=self.outsider, created_by=self.outsider, title="Autre service")
        grant_activity_role(profile=self.outsider, activity=other_activity)
        other_service = create_service_details(activity=other_activity, actor=self.outsider, service_kind=ServiceKind.CAREER_SUPPORT)
        other_journey = create_service_journey(service=other_service, initiated_by=self.outsider, beneficiary=self.outsider)
        from journeys.collaboration_services import create_step
        foreign_step = create_step(journey=other_journey, title="Foreign", kind=JourneyStepKind.PAYMENT, created_by=self.outsider)
        with self.assertRaises(ValidationError):
            create_requirement_payment_obligation(
                assessment=self.assessment,
                actor=self.manager,
                step=foreign_step,
                amount=Decimal("50.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.EXTERNAL,
                external_payee_name="Université X",
                source_key="t33:foreign-step",
            )
        with self.assertRaises(PermissionDenied):
            create_requirement_payment_obligation(
                assessment=self.assessment,
                actor=self.outsider,
                step=self.payment_step,
                amount=Decimal("50.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.EXTERNAL,
                external_payee_name="Université X",
                source_key="t33:idor-obligation",
            )


class ServiceT33SubmissionOutcomeTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="t33-submit-manager", email="t33-submit-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t33-submit-beneficiary", email="t33-submit-beneficiary@example.com", password="x")
        self.outsider = User.objects.create_user(username="t33-submit-outsider", email="t33-submit-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Candidature externe T33")
        grant_activity_role(profile=self.manager, activity=self.activity)
        self.service = create_service_details(
            activity=self.activity,
            actor=self.manager,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            completion_policy=CompletionPolicy.REQUIRED_STEPS_AND_SUBMISSION,
        )
        template = create_plan_template(service=self.service, actor=self.manager, key="application", name="Candidature externe")
        add_template_step(template=template, actor=self.manager, title="Préparer candidature", position=10)
        self.template = publish_plan_template(template=template, actor=self.manager)
        journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, template=self.template)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        self.journey = start_service_journey(journey=confirmed, actor=self.manager)
        self.context = self.journey.service_context
        self.step = self.journey.steps.get(title="Préparer candidature")
        start_step(step=self.step, actor=self.manager)
        complete_service_step(step=self.step, actor=self.manager)

    def test_submission_required_for_fulfillment_then_unsuccessful_outcome_keeps_journey_fulfilled(self):
        with self.assertRaises(ValidationError):
            fulfill_service_journey(journey=self.journey, actor=self.manager)
        receipt = create_artifact(journey=self.journey, uploaded_file=pdf_upload("submission.pdf"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.OTHER, title="Accusé de soumission")
        submission = prepare_service_submission(context=self.context, actor=self.manager, mode=ServiceSubmissionMode.EXTERNAL_WEB, receipt_artifact=receipt)
        self.assertEqual(submission.attempt, 1)
        submission = submit_service_submission(submission=submission, actor=self.manager, external_reference="APP-001")
        submission = acknowledge_service_submission(submission=submission, actor=self.manager)
        self.assertEqual(submission.status, ServiceSubmissionStatus.ACKNOWLEDGED)
        fulfilled = fulfill_service_journey(journey=self.journey, actor=self.manager)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)
        record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.UNDER_REVIEW, occurred_at=timezone.now() + timedelta(minutes=1))
        record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.INTERVIEW, occurred_at=timezone.now() + timedelta(minutes=2))
        record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.UNSUCCESSFUL, occurred_at=timezone.now() + timedelta(minutes=3))
        self.context.refresh_from_db()
        fulfilled.refresh_from_db()
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)
        self.assertEqual(self.context.current_outcome, ServiceCurrentOutcome.UNSUCCESSFUL)

    def test_successful_external_outcome_never_fulfills_journey_automatically(self):
        record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.SUCCESSFUL, occurred_at=timezone.now())
        self.context.refresh_from_db()
        self.journey.refresh_from_db()
        self.assertEqual(self.context.current_outcome, ServiceCurrentOutcome.SUCCESSFUL)
        self.assertEqual(self.journey.status, JourneyStatus.IN_PROGRESS)

    def test_late_old_outcome_does_not_regress_projection_and_events_are_append_only(self):
        now = timezone.now()
        newest = record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.INTERVIEW, occurred_at=now)
        old = record_service_outcome(context=self.context, actor=self.manager, event_type=ServiceOutcomeEventType.SUBMITTED, occurred_at=now - timedelta(days=2))
        self.context.refresh_from_db()
        self.assertEqual(self.context.current_outcome, ServiceCurrentOutcome.INTERVIEW)
        old.note = "mutation interdite"
        with self.assertRaises(ValidationError):
            old.save()
        with self.assertRaises(ValidationError):
            newest.delete()

    def test_submission_attempts_preserve_failed_history_and_increment(self):
        from .t33_services import fail_service_submission
        first = prepare_service_submission(context=self.context, actor=self.manager, mode=ServiceSubmissionMode.EMAIL)
        fail_service_submission(submission=first, actor=self.manager, failure_reason="Adresse rejetée")
        second = prepare_service_submission(context=self.context, actor=self.manager, mode=ServiceSubmissionMode.EXTERNAL_WEB)
        self.assertEqual(second.attempt, 2)
        first.refresh_from_db()
        self.assertEqual(first.status, ServiceSubmissionStatus.FAILED)

    def test_submission_and_outcome_idor_boundaries(self):
        other_journey = create_service_journey(service=self.service, initiated_by=self.outsider, beneficiary=self.outsider, template=self.template)
        foreign_receipt = create_artifact(journey=other_journey, uploaded_file=pdf_upload("foreign.pdf"), uploaded_by=self.outsider, kind=JourneyArtifactKind.OTHER, title="Foreign")
        with self.assertRaises(PermissionDenied):
            prepare_service_submission(context=self.context, actor=self.manager, mode=ServiceSubmissionMode.EMAIL, receipt_artifact=foreign_receipt)
        with self.assertRaises(PermissionDenied):
            record_service_outcome(context=self.context, actor=self.outsider, event_type=ServiceOutcomeEventType.SUCCESSFUL, occurred_at=timezone.now())
