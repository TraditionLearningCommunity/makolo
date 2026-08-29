from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.services import grant_activity_role
from domain_events.models import DomainEventOutbox
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility, JourneyStepKind
from journeys.collaboration_services import assign_journey, complete_step, create_artifact, start_step
from journeys.models import JourneyStatus
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import add_requirement, create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision
from requirements.contracts import RequirementAssessmentState

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementAssessment, ServiceRequirementEvidence, ServiceRequirementEvidenceStatus
from .requirement_consequences import ServiceRequirementConsequence
from .services import (
    add_template_step,
    adopt_opportunity_revision,
    assess_requirement,
    attach_opportunity_to_service_journey,
    create_plan_template,
    create_requirement_step,
    create_service_details,
    create_service_journey,
    derive_requirement_consequence,
    fulfill_service_journey,
    has_newer_opportunity_revision,
    publish_plan_template,
    requirement_progress,
    review_requirement_evidence,
    start_service_journey,
    submit_requirement_evidence,
    submit_service_journey,
)


User = get_user_model()


def pdf_upload(text=b"Makolo evidence"):
    return SimpleUploadedFile("evidence.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class ServiceOpportunityRequirementTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="t32-curator", email="t32-curator@example.com", password="x", is_superuser=True, is_staff=True)
        self.manager = User.objects.create_user(username="t32-manager", email="t32-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t32-beneficiary", email="t32-beneficiary@example.com", password="x")
        self.other_beneficiary = User.objects.create_user(username="t32-beneficiary-2", email="t32-beneficiary-2@example.com", password="x")
        self.outsider = User.objects.create_user(username="t32-outsider", email="t32-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Accompagnement candidature emploi")
        grant_activity_role(profile=self.manager, activity=self.activity)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT, opportunity_policy=OpportunityPolicy.REQUIRED)
        template = create_plan_template(service=self.service, actor=self.manager, key="job", name="Candidature emploi")
        add_template_step(template=template, actor=self.manager, title="Préparer le dossier", position=10)
        self.template = publish_plan_template(template=template, actor=self.manager)
        self.opportunity, self.revision = self._published_opportunity()

    def _published_opportunity(self, *, kind=OpportunityKind.JOB, requirement_titles=("CV", "Expérience")):
        opportunity = create_opportunity(actor=self.curator, kind=kind)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.curator, title=f"{kind} — T32", issuer_name="Émetteur externe", summary="Opportunity externe T32", timezone_name="Africa/Lubumbashi")
        create_opportunity_source(opportunity=opportunity, actor=self.curator, source_type=OpportunitySourceType.OFFICIAL, source_name="Site officiel", url=f"https://example.test/opportunities/{opportunity.pk}", is_primary=True, verified=True)
        for position, title in enumerate(requirement_titles, start=1):
            if title == "CV":
                req_kind = OpportunityRequirementKind.DOCUMENT
            elif "Expérience" in title:
                req_kind = OpportunityRequirementKind.EXPERIENCE
            elif "Financial" in title:
                req_kind = OpportunityRequirementKind.FINANCIAL
            else:
                req_kind = OpportunityRequirementKind.EDUCATION
            add_requirement(revision=revision, actor=self.curator, kind=req_kind, title=title, position=position * 10)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.curator)
        return opportunity, revision

    def _case(self, *, beneficiary=None, opportunity=None):
        beneficiary = beneficiary or self.beneficiary
        opportunity = opportunity if opportunity is not None else self.opportunity
        journey = create_service_journey(service=self.service, initiated_by=beneficiary, beneficiary=beneficiary, template=self.template, opportunity=opportunity)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        return journey

    def test_required_policy_blocks_start_until_opportunity_is_attached(self):
        journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, template=self.template)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        self.assertIsNone(journey.service_context.opportunity_id)
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        with self.assertRaises(ValidationError):
            start_service_journey(journey=confirmed, actor=self.manager)
        attach_opportunity_to_service_journey(context=confirmed.service_context, opportunity=self.opportunity, actor=self.beneficiary)
        confirmed.service_context.refresh_from_db()
        self.assertEqual(confirmed.service_context.opportunity_revision_id, self.revision.pk)
        started = start_service_journey(journey=confirmed, actor=self.manager)
        self.assertEqual(started.status, JourneyStatus.IN_PROGRESS)

    def test_required_pins_current_revision_and_materializes_assessments(self):
        journey = self._case()
        context = journey.service_context
        self.assertEqual(context.opportunity_id, self.opportunity.pk)
        self.assertEqual(context.opportunity_revision_id, self.revision.pk)
        self.assertEqual(ServiceRequirementAssessment.objects.filter(context=context).count(), self.revision.requirements.count())

    def test_optional_and_none_policies_are_explicit(self):
        optional_activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Service optional")
        grant_activity_role(profile=self.manager, activity=optional_activity)
        optional = create_service_details(activity=optional_activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT, opportunity_policy=OpportunityPolicy.OPTIONAL)
        without = create_service_journey(service=optional, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        self.assertIsNone(without.service_context.opportunity_id)
        with_opp = create_service_journey(service=optional, initiated_by=self.other_beneficiary, beneficiary=self.other_beneficiary, opportunity=self.opportunity)
        self.assertEqual(with_opp.service_context.opportunity_revision_id, self.revision.pk)

        none_activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Service sans Opportunity")
        grant_activity_role(profile=self.manager, activity=none_activity)
        none_service = create_service_details(activity=none_activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT, opportunity_policy=OpportunityPolicy.NONE)
        create_service_journey(service=none_service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        with self.assertRaises(ValidationError):
            create_service_journey(service=none_service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, opportunity=self.opportunity)

    def test_revision_n_stays_pinned_until_explicit_adoption_and_history_survives(self):
        journey = self._case()
        context = journey.service_context
        assessment_n = context.requirement_assessments.select_related("requirement").order_by("requirement__position").first()
        assess_requirement(assessment=assessment_n, actor=self.manager, status=RequirementAssessmentState.SATISFIED, note="Condition vérifiée sur N.")
        artifact = create_artifact(journey=journey, uploaded_file=pdf_upload(), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV")
        evidence = submit_requirement_evidence(assessment=assessment_n, artifact=artifact, actor=self.beneficiary)
        step_link = create_requirement_step(assessment=context.requirement_assessments.exclude(pk=assessment_n.pk).first(), actor=self.manager, title="Vérifier l’expérience")

        revision2 = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Opportunity v2", issuer_name="Émetteur externe", timezone_name="Africa/Lubumbashi", change_summary="Nouveaux critères")
        add_requirement(revision=revision2, actor=self.curator, kind=OpportunityRequirementKind.DOCUMENT, title="CV actualisé", position=10)
        add_requirement(revision=revision2, actor=self.curator, kind=OpportunityRequirementKind.LANGUAGE, title="Français B2", position=20)
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision2, actor=self.curator)

        context.refresh_from_db()
        self.assertTrue(has_newer_opportunity_revision(context))
        self.assertEqual(context.opportunity_revision_id, self.revision.pk)
        adopt_opportunity_revision(context=context, revision=revision2, actor=self.manager)
        context.refresh_from_db()
        self.assertFalse(has_newer_opportunity_revision(context))
        self.assertEqual(context.opportunity_revision_id, revision2.pk)
        self.assertEqual(context.opportunity_revision_adoptions.count(), 1)
        self.assertEqual(context.requirement_assessments.filter(requirement__revision=revision2).count(), 2)
        self.assertTrue(ServiceRequirementAssessment.objects.filter(pk=assessment_n.pk).exists())
        self.assertTrue(ServiceRequirementEvidence.objects.filter(pk=evidence.pk).exists())
        self.assertTrue(journey.steps.filter(pk=step_link.journey_step_id).exists())
        self.assertTrue(DomainEventOutbox.objects.filter(event_type="service.opportunity_revision.adopted", source_id=str(context.pk)).exists())
        with self.assertRaises(ValidationError):
            assess_requirement(assessment=assessment_n, actor=self.manager, status=RequirementAssessmentState.PENDING)

    def test_evidence_uses_canonical_artifacts_and_enforces_case_boundaries(self):
        journey = self._case()
        assessment = journey.service_context.requirement_assessments.order_by("created_at").first()
        artifact = create_artifact(journey=journey, uploaded_file=pdf_upload(b"own"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV")
        evidence = submit_requirement_evidence(assessment=assessment, artifact=artifact, actor=self.beneficiary)
        reviewed = review_requirement_evidence(evidence=evidence, actor=self.manager, decision=ServiceRequirementEvidenceStatus.ACCEPTED, review_note="Pièce vérifiée.")
        self.assertEqual(reviewed.status, ServiceRequirementEvidenceStatus.ACCEPTED)
        self.assertNotEqual(artifact.status, reviewed.status)

        other_journey = self._case(beneficiary=self.other_beneficiary)
        other_artifact = create_artifact(journey=other_journey, uploaded_file=pdf_upload(b"other"), uploaded_by=self.other_beneficiary, kind=JourneyArtifactKind.CV, title="Autre CV")
        with self.assertRaises(PermissionDenied):
            submit_requirement_evidence(assessment=assessment, artifact=other_artifact, actor=self.beneficiary)
        with self.assertRaises(PermissionDenied):
            assess_requirement(assessment=assessment, actor=self.outsider, status=RequirementAssessmentState.SATISFIED)

    def test_progress_and_requirement_steps_are_derived_and_idempotent(self):
        journey = self._case()
        context = journey.service_context
        assessments = list(context.requirement_assessments.select_related("requirement").order_by("requirement__position"))
        initial = requirement_progress(context)
        self.assertEqual(initial["total"], 2)
        self.assertEqual(initial["unassessed"], 2)
        first = assess_requirement(assessment=assessments[0], actor=self.manager, status=RequirementAssessmentState.PENDING)
        link = create_requirement_step(assessment=first, actor=self.manager, title="Préparer la preuve")
        same = create_requirement_step(assessment=first, actor=self.manager, title="Ne pas dupliquer")
        self.assertEqual(link.pk, same.pk)
        self.assertEqual(link.assessment_id, first.pk)
        self.assertEqual(link.journey_step.journey_id, journey.pk)
        self.assertEqual(link.journey_step.kind, JourneyStepKind.DOCUMENT)
        self.assertEqual(derive_requirement_consequence(first), ServiceRequirementConsequence.ACTION_REQUIRED)
        progress = requirement_progress(context)
        self.assertEqual(progress["pending"], 1)
        self.assertEqual(progress["unassessed"], 1)
        self.assertFalse(progress["complete"])

    def test_financial_requirement_creates_payment_step_but_no_payment(self):
        opportunity, _ = self._published_opportunity(requirement_titles=("Financial fees",))
        journey = self._case(opportunity=opportunity)
        assessment = journey.service_context.requirement_assessments.get()
        assess_requirement(assessment=assessment, actor=self.manager, status=RequirementAssessmentState.PENDING)
        link = create_requirement_step(assessment=assessment, actor=self.manager, title="Payer les frais de candidature")
        self.assertEqual(link.journey_step.kind, JourneyStepKind.PAYMENT)
        from payments.models import Payment
        if any(field.name == "journey" for field in Payment._meta.fields):
            self.assertEqual(Payment.objects.filter(journey=journey).count(), 0)

    def test_not_eligible_is_derived_from_unsatisfied_eligibility_and_does_not_reject_journey(self):
        opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.curator, title="Eligibility T34A", issuer_name="Émetteur externe", timezone_name="Africa/Lubumbashi")
        add_requirement(revision=revision, actor=self.curator, kind=OpportunityRequirementKind.ELIGIBILITY, title="Critère d’éligibilité", position=10)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.curator)
        journey = self._case(opportunity=opportunity)
        assessment = journey.service_context.requirement_assessments.get()
        assess_requirement(assessment=assessment, actor=self.manager, status=RequirementAssessmentState.UNSATISFIED)
        self.assertEqual(derive_requirement_consequence(assessment), ServiceRequirementConsequence.NOT_ELIGIBLE)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.DRAFT)

    def test_required_requirements_block_fulfillment_until_satisfied(self):
        journey = self._case()
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        started = start_service_journey(journey=confirmed, actor=self.manager)
        step = started.steps.get(title="Préparer le dossier")
        start_step(step=step, actor=self.manager)
        complete_step(step=step, actor=self.manager)
        with self.assertRaises(ValidationError):
            fulfill_service_journey(journey=started, actor=self.manager)
        for assessment in started.service_context.requirement_assessments.filter(requirement__revision=self.revision):
            assess_requirement(assessment=assessment, actor=self.manager, status=RequirementAssessmentState.SATISFIED)
        fulfilled = fulfill_service_journey(journey=started, actor=self.manager)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)

    def test_scholarship_uses_same_engine(self):
        scholarship, revision = self._published_opportunity(kind=OpportunityKind.SCHOLARSHIP, requirement_titles=("CV", "Diplôme", "Financial fees"))
        journey = self._case(opportunity=scholarship)
        self.assertEqual(journey.service_context.opportunity_revision_id, revision.pk)
        self.assertEqual(journey.service_context.requirement_assessments.count(), 3)
