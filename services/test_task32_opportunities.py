from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.services import grant_activity_role
from domain_events.models import DomainEventOutbox
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, complete_step, create_artifact, start_step
from journeys.models import JourneyStatus
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import add_requirement, create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementAssessment, ServiceRequirementAssessmentStatus, ServiceRequirementEvidence, ServiceRequirementEvidenceStatus
from .services import add_template_step, adopt_opportunity_revision, assess_requirement, create_plan_template, create_service_details, create_service_journey, fulfill_service_journey, publish_plan_template, review_requirement_evidence, start_service_journey, submit_requirement_evidence, submit_service_journey


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
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.curator, title="Développeur backend", issuer_name="Employeur externe", summary="Opportunity externe pour le scénario T32.", timezone_name="Africa/Lubumbashi")
        create_opportunity_source(opportunity=opportunity, actor=self.curator, source_type=OpportunitySourceType.OFFICIAL, source_name="Site officiel", url=f"https://example.test/opportunities/{opportunity.pk}", is_primary=True, verified=True)
        for position, title in enumerate(requirement_titles, start=1):
            add_requirement(revision=revision, actor=self.curator, kind=OpportunityRequirementKind.DOCUMENT if title == "CV" else OpportunityRequirementKind.EXPERIENCE, title=title, position=position * 10)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.curator)
        return opportunity, revision

    def _case(self, *, beneficiary=None):
        beneficiary = beneficiary or self.beneficiary
        journey = create_service_journey(service=self.service, initiated_by=beneficiary, beneficiary=beneficiary, template=self.template, opportunity=self.opportunity)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        return journey

    def test_required_policy_pins_published_revision_and_materializes_assessments(self):
        with self.assertRaises(ValidationError):
            create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, template=self.template)
        journey = self._case()
        context = journey.service_context
        self.assertEqual(context.opportunity_id, self.opportunity.pk)
        self.assertEqual(context.opportunity_revision_id, self.revision.pk)
        self.assertEqual(ServiceRequirementAssessment.objects.filter(context=context).count(), self.revision.requirements.count())

        none_activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Service sans Opportunity")
        grant_activity_role(profile=self.manager, activity=none_activity)
        none_service = create_service_details(activity=none_activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT, opportunity_policy=OpportunityPolicy.NONE)
        with self.assertRaises(ValidationError):
            create_service_journey(service=none_service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, opportunity=self.opportunity)

    def test_revision_n_stays_pinned_until_explicit_adoption_and_history_survives(self):
        journey = self._case()
        context = journey.service_context
        assessment_n = context.requirement_assessments.select_related("requirement").order_by("requirement__position").first()
        assess_requirement(assessment=assessment_n, actor=self.manager, status=ServiceRequirementAssessmentStatus.SATISFIED, note="Condition vérifiée sur N.")
        artifact = create_artifact(journey=journey, uploaded_file=pdf_upload(), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV")
        evidence = submit_requirement_evidence(assessment=assessment_n, artifact=artifact, actor=self.beneficiary)

        revision2 = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Développeur backend — mise à jour", issuer_name="Employeur externe", timezone_name="Africa/Lubumbashi", change_summary="Nouveaux critères")
        add_requirement(revision=revision2, actor=self.curator, kind=OpportunityRequirementKind.DOCUMENT, title="CV actualisé", position=10)
        add_requirement(revision=revision2, actor=self.curator, kind=OpportunityRequirementKind.LANGUAGE, title="Français B2", position=20)
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision2, actor=self.curator)

        context.refresh_from_db()
        self.assertEqual(context.opportunity_revision_id, self.revision.pk)
        self.assertEqual(context.requirement_assessments.filter(requirement__revision=self.revision).count(), 2)
        adopt_opportunity_revision(context=context, revision=revision2, actor=self.manager)
        context.refresh_from_db()
        self.assertEqual(context.opportunity_revision_id, revision2.pk)
        self.assertEqual(context.requirement_assessments.filter(requirement__revision=revision2).count(), 2)
        self.assertTrue(ServiceRequirementAssessment.objects.filter(pk=assessment_n.pk).exists())
        self.assertTrue(ServiceRequirementEvidence.objects.filter(pk=evidence.pk).exists())
        self.assertTrue(DomainEventOutbox.objects.filter(event_type="service.opportunity_revision.adopted", source_id=str(context.pk)).exists())
        with self.assertRaises(ValidationError):
            assess_requirement(assessment=assessment_n, actor=self.manager, status=ServiceRequirementAssessmentStatus.ACTION_REQUIRED)

    def test_evidence_uses_canonical_journey_artifacts_and_enforces_case_boundaries(self):
        journey = self._case()
        assessment = journey.service_context.requirement_assessments.order_by("created_at").first()
        artifact = create_artifact(journey=journey, uploaded_file=pdf_upload(b"own"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV")
        evidence = submit_requirement_evidence(assessment=assessment, artifact=artifact, actor=self.beneficiary)
        self.assertEqual(evidence.status, ServiceRequirementEvidenceStatus.SUBMITTED)
        reviewed = review_requirement_evidence(evidence=evidence, actor=self.manager, decision=ServiceRequirementEvidenceStatus.ACCEPTED, review_note="Pièce vérifiée.")
        self.assertEqual(reviewed.status, ServiceRequirementEvidenceStatus.ACCEPTED)

        other_journey = self._case(beneficiary=self.other_beneficiary)
        other_artifact = create_artifact(journey=other_journey, uploaded_file=pdf_upload(b"other"), uploaded_by=self.other_beneficiary, kind=JourneyArtifactKind.CV, title="Autre CV")
        with self.assertRaises(PermissionDenied):
            submit_requirement_evidence(assessment=assessment, artifact=other_artifact, actor=self.beneficiary)
        with self.assertRaises(PermissionDenied):
            assess_requirement(assessment=assessment, actor=self.outsider, status=ServiceRequirementAssessmentStatus.SATISFIED)

    def test_required_requirements_block_fulfillment_until_satisfied(self):
        journey = self._case()
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        self.assertEqual(confirmed.status, JourneyStatus.CONFIRMED)
        started = start_service_journey(journey=confirmed, actor=self.manager)
        step = started.steps.get(title="Préparer le dossier")
        start_step(step=step, actor=self.manager)
        complete_step(step=step, actor=self.manager)
        with self.assertRaises(ValidationError):
            fulfill_service_journey(journey=started, actor=self.manager)
        for assessment in started.service_context.requirement_assessments.filter(requirement__revision=self.revision):
            assess_requirement(assessment=assessment, actor=self.manager, status=ServiceRequirementAssessmentStatus.SATISFIED)
        fulfilled = fulfill_service_journey(journey=started, actor=self.manager)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)

    def test_scholarship_opportunity_uses_same_requirement_engine(self):
        scholarship, revision = self._published_opportunity(kind=OpportunityKind.SCHOLARSHIP, requirement_titles=("CV", "Diplôme"))
        journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, template=self.template, opportunity=scholarship)
        self.assertEqual(journey.service_context.opportunity_revision_id, revision.pk)
        self.assertEqual(journey.service_context.requirement_assessments.count(), 2)
