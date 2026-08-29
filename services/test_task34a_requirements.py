import importlib
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact
from opportunities.models import OpportunityKind, OpportunityRequirementKind
from opportunities.services import add_requirement, create_opportunity, create_opportunity_revision, publish_opportunity_revision
from payments.models import PaymentObligationProcessingMode
from requirements.contracts import RequirementAssessmentState

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementAssessment, ServiceRequirementEvidence, ServiceRequirementStepLink
from .requirement_consequences import ServiceRequirementConsequence
from .requirement_services import (
    assess_requirement,
    create_requirement_step,
    derive_requirement_consequence,
    requirement_progress,
    submit_requirement_evidence,
)
from .services import create_service_details, create_service_journey
from .t33_services import create_requirement_payment_obligation


User = get_user_model()


def pdf_upload():
    return SimpleUploadedFile(
        "evidence.pdf",
        b"%PDF-1.4\nT34A evidence\n%%EOF",
        content_type="application/pdf",
    )


class ServiceHorizontalRequirementTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="t34a-curator", email="t34a-curator@example.com", password="x", is_staff=True, is_superuser=True)
        self.manager = User.objects.create_user(username="t34a-manager", email="t34a-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34a-beneficiary", email="t34a-beneficiary@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Requirements T34A")
        grant_activity_role(profile=self.manager, activity=self.activity)
        self.service = create_service_details(
            activity=self.activity,
            actor=self.manager,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        self.opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.SCHOLARSHIP)
        self.revision = create_opportunity_revision(
            opportunity=self.opportunity,
            actor=self.curator,
            title="Requirements T34A",
            issuer_name="External issuer",
            timezone_name="Africa/Lubumbashi",
        )
        self.requirements = []
        kinds = [
            OpportunityRequirementKind.DOCUMENT,
            OpportunityRequirementKind.EXPERIENCE,
            OpportunityRequirementKind.FINANCIAL,
            OpportunityRequirementKind.ELIGIBILITY,
            OpportunityRequirementKind.EDUCATION,
            OpportunityRequirementKind.LANGUAGE,
        ]
        for position, kind in enumerate(kinds, start=1):
            self.requirements.append(
                add_requirement(
                    revision=self.revision,
                    actor=self.curator,
                    kind=kind,
                    title=f"Requirement {position}",
                    position=position * 10,
                )
            )
        publish_opportunity_revision(opportunity=self.opportunity, revision=self.revision, actor=self.curator)
        self.journey = create_service_journey(
            service=self.service,
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            opportunity=self.opportunity,
        )
        assign_journey(
            journey=self.journey,
            profile=self.manager,
            responsibility=JourneyAssignmentResponsibility.LEAD,
            is_primary=True,
            assigned_by=self.manager,
        )
        self.context = self.journey.service_context
        self.assessments = list(
            self.context.requirement_assessments.select_related("requirement").order_by("requirement__position")
        )

    def test_progress_uses_only_fundamental_states(self):
        states = [
            RequirementAssessmentState.UNASSESSED,
            RequirementAssessmentState.PENDING,
            RequirementAssessmentState.SATISFIED,
            RequirementAssessmentState.UNSATISFIED,
            RequirementAssessmentState.NOT_APPLICABLE,
            RequirementAssessmentState.SATISFIED,
        ]
        for assessment, state in zip(self.assessments, states):
            assess_requirement(assessment=assessment, actor=self.manager, status=state)
        progress = requirement_progress(self.context)
        self.assertEqual(progress["unassessed"], 1)
        self.assertEqual(progress["pending"], 1)
        self.assertEqual(progress["satisfied"], 2)
        self.assertEqual(progress["unsatisfied"], 1)
        self.assertEqual(progress["not_applicable"], 1)
        self.assertFalse(progress["complete"])
        self.assertNotIn("action_required", progress)
        self.assertNotIn("needs_review", progress)
        self.assertNotIn("not_eligible", progress)

    def test_consequences_are_derived_from_canonical_relations(self):
        document = self.assessments[0]
        assess_requirement(assessment=document, actor=self.manager, status=RequirementAssessmentState.PENDING)
        step_link = create_requirement_step(assessment=document, actor=self.manager, title="Provide document")
        self.assertEqual(derive_requirement_consequence(document), ServiceRequirementConsequence.ACTION_REQUIRED)

        evidence_assessment = self.assessments[1]
        assess_requirement(assessment=evidence_assessment, actor=self.manager, status=RequirementAssessmentState.PENDING)
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.OTHER,
            title="Requirement evidence",
        )
        submit_requirement_evidence(assessment=evidence_assessment, artifact=artifact, actor=self.beneficiary)
        self.assertEqual(derive_requirement_consequence(evidence_assessment), ServiceRequirementConsequence.NEEDS_REVIEW)

        financial = self.assessments[2]
        assess_requirement(assessment=financial, actor=self.manager, status=RequirementAssessmentState.PENDING)
        payment_step = create_requirement_step(assessment=financial, actor=self.manager, title="Pay fee")
        create_requirement_payment_obligation(
            assessment=financial,
            actor=self.manager,
            step=payment_step.journey_step,
            amount=Decimal("25.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            external_payee_name="External institution",
            source_key="t34a:test:payment",
        )
        financial.refresh_from_db()
        self.assertEqual(financial.status, RequirementAssessmentState.PENDING)
        self.assertEqual(derive_requirement_consequence(financial), ServiceRequirementConsequence.PAYMENT_REQUIRED)

        eligibility = self.assessments[3]
        assess_requirement(assessment=eligibility, actor=self.manager, status=RequirementAssessmentState.UNSATISFIED)
        self.assertEqual(derive_requirement_consequence(eligibility), ServiceRequirementConsequence.NOT_ELIGIBLE)

        satisfied = self.assessments[4]
        assess_requirement(assessment=satisfied, actor=self.manager, status=RequirementAssessmentState.SATISFIED)
        self.assertIsNone(derive_requirement_consequence(satisfied))

        not_applicable = self.assessments[5]
        assess_requirement(assessment=not_applicable, actor=self.manager, status=RequirementAssessmentState.NOT_APPLICABLE)
        self.assertIsNone(derive_requirement_consequence(not_applicable))
        self.assertTrue(ServiceRequirementStepLink.objects.filter(pk=step_link.pk).exists())


class ServiceRequirementStateMigrationTests(ServiceHorizontalRequirementTests):
    def test_historical_states_map_in_place_and_preserve_audit_and_relations(self):
        historical_states = [
            "unassessed",
            "satisfied",
            "action_required",
            "needs_review",
            "not_applicable",
            "not_eligible",
        ]
        expected_states = [
            "unassessed",
            "satisfied",
            "pending",
            "pending",
            "not_applicable",
            "unsatisfied",
        ]
        observed_at = timezone.now()
        snapshots = {}
        for assessment, old_state in zip(self.assessments, historical_states):
            values = {
                "status": old_state,
                "note": f"historical:{old_state}",
                "assessed_by": None if old_state == "unassessed" else self.manager,
                "assessed_at": None if old_state == "unassessed" else observed_at,
            }
            ServiceRequirementAssessment.objects.filter(pk=assessment.pk).update(**values)
            assessment.refresh_from_db()
            snapshots[assessment.pk] = {
                "context_id": assessment.context_id,
                "requirement_id": assessment.requirement_id,
                "note": assessment.note,
                "assessed_by_id": assessment.assessed_by_id,
                "assessed_at": assessment.assessed_at,
                "created_at": assessment.created_at,
            }

        linked = self.assessments[2]
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.OTHER,
            title="Historical relation evidence",
        )
        evidence = ServiceRequirementEvidence.objects.create(
            assessment=linked,
            artifact=artifact,
            submitted_by=self.beneficiary,
        )
        step_link = create_requirement_step(assessment=linked, actor=self.manager, title="Historical linked step")
        payment_link = create_requirement_payment_obligation(
            assessment=linked,
            actor=self.manager,
            step=step_link.journey_step,
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            external_payee_name="Historical payee",
            source_key="t34a:migration:payment",
        )
        # Restore the historical pseudo-state after relationship services applied current semantics.
        ServiceRequirementAssessment.objects.filter(pk=linked.pk).update(
            status="action_required",
            note="historical:action_required",
            assessed_by=self.manager,
            assessed_at=observed_at,
        )
        snapshots[linked.pk].update(
            note="historical:action_required",
            assessed_by_id=self.manager.pk,
            assessed_at=observed_at,
        )

        migration = importlib.import_module("services.migrations.0004_horizontal_requirement_states")
        schema_editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        migration.migrate_requirement_assessment_states(apps, schema_editor)

        migrated = list(ServiceRequirementAssessment.objects.filter(pk__in=snapshots).order_by("requirement__position"))
        self.assertEqual([item.status for item in migrated], expected_states)
        self.assertEqual({item.pk for item in migrated}, set(snapshots))
        for item in migrated:
            snapshot = snapshots[item.pk]
            self.assertEqual(item.context_id, snapshot["context_id"])
            self.assertEqual(item.requirement_id, snapshot["requirement_id"])
            self.assertEqual(item.note, snapshot["note"])
            self.assertEqual(item.assessed_by_id, snapshot["assessed_by_id"])
            self.assertEqual(item.assessed_at, snapshot["assessed_at"])
            self.assertEqual(item.created_at, snapshot["created_at"])

        self.assertTrue(ServiceRequirementEvidence.objects.filter(pk=evidence.pk, assessment_id=linked.pk).exists())
        self.assertTrue(ServiceRequirementStepLink.objects.filter(pk=step_link.pk, assessment_id=linked.pk).exists())
        self.assertTrue(type(payment_link).objects.filter(pk=payment_link.pk, assessment_id=linked.pk).exists())

    def test_unknown_historical_state_fails_explicitly(self):
        assessment = self.assessments[0]
        ServiceRequirementAssessment.objects.filter(pk=assessment.pk).update(status="mystery_state")
        migration = importlib.import_module("services.migrations.0004_horizontal_requirement_states")
        schema_editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        with self.assertRaisesRegex(RuntimeError, "mystery_state"):
            migration.migrate_requirement_assessment_states(apps, schema_editor)
