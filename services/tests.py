from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactReviewStatus,
    JourneyAssignmentResponsibility,
    JourneyBlockerStatus,
    JourneyStepKind,
    JourneyStepStatus,
)
from journeys.collaboration_services import (
    assign_journey,
    complete_step,
    create_artifact,
    create_artifact_version,
    create_blocker,
    decide_artifact_review,
    request_artifact_review,
    resolve_blocker,
    start_step,
)
from journeys.models import JourneyStatus, WorkflowKind

from .models import (
    IntakePolicy,
    OpportunityPolicy,
    ServiceDetails,
    ServiceIntakeQuestion,
    ServiceIntakeQuestionType,
    ServiceJourneyContext,
    ServiceKind,
    ServicePlanMaterialization,
    ServicePlanTemplateStatus,
)
from .services import (
    add_template_dependency,
    add_template_step,
    answer_intake_question,
    create_plan_template,
    create_plan_template_version,
    create_service_details,
    create_service_journey,
    fulfill_service_journey,
    materialize_service_plan,
    publish_plan_template,
    start_service_journey,
    submit_service_journey,
)


User = get_user_model()


def pdf_upload(text=b"CV Makolo"):
    return SimpleUploadedFile("cv.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class ServiceFixtureMixin:
    def build_fixture(self):
        self.manager = User.objects.create_user(username="services-manager", email="services-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="services-beneficiary", email="services-beneficiary@example.com", password="x")
        self.reviewer = User.objects.create_user(username="services-reviewer", email="services-reviewer@example.com", password="x")
        self.outsider = User.objects.create_user(username="services-outsider", email="services-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Refaire mon CV")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        grant_activity_role(profile=self.reviewer, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT, opportunity_policy=OpportunityPolicy.NONE, intake_policy=IntakePolicy.AUTO_CONFIRM)

    def build_published_template(self):
        template = create_plan_template(service=self.service, actor=self.manager, key="cv-support", name="Accompagnement CV")
        prep = add_template_step(template=template, actor=self.manager, title="Clarifier l’objectif", kind=JourneyStepKind.ACTION, position=10)
        document = add_template_step(template=template, actor=self.manager, title="Préparer CV", kind=JourneyStepKind.DOCUMENT, position=20)
        final = add_template_step(template=template, actor=self.manager, title="Finaliser le dossier", kind=JourneyStepKind.ACTION, position=30)
        add_template_dependency(step=document, depends_on=prep, actor=self.manager)
        add_template_dependency(step=final, depends_on=document, actor=self.manager)
        publish_plan_template(template=template, actor=self.manager)
        return template

    def create_case(self, template=None):
        journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, objective="Obtenir un CV clair pour mes candidatures.", template=template)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        assign_journey(journey=journey, profile=self.reviewer, responsibility=JourneyAssignmentResponsibility.REVIEWER, assigned_by=self.manager)
        return journey


class ServiceDetailsAndContextTests(ServiceFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_service_details_specializes_activity_without_parallel_ownership(self):
        self.assertEqual(self.service.activity, self.activity)
        self.assertEqual(ServiceDetails.objects.filter(activity=self.activity).count(), 1)
        field_names = {field.name for field in ServiceDetails._meta.get_fields()}
        for forbidden in {"owner", "owner_profile", "participant", "price", "currency", "payment", "status"}:
            self.assertNotIn(forbidden, field_names)
        ordinary = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Activity non-Service")
        with self.assertRaises(ServiceDetails.DoesNotExist):
            _ = ordinary.service_details

    def test_context_requires_service_workflow_and_service_activity(self):
        template = self.build_published_template()
        journey = self.create_case(template)
        context = journey.service_context
        self.assertEqual(journey.workflow, WorkflowKind.SERVICE)
        self.assertEqual(context.service_plan_template, template)
        self.assertIn("CV clair", context.objective)
        self.assertIsNone(context.opportunity_id)
        self.assertIsNone(context.opportunity_revision_id)
        from journeys.services import create_journey
        legacy = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.REGISTRATION)
        with self.assertRaises(ValidationError):
            ServiceJourneyContext(journey=legacy).save()

    def test_required_opportunity_policy_blocks_operational_start_without_link(self):
        other_activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Service nécessitant une Opportunity")
        grant_activity_role(profile=self.manager, activity=other_activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        service = create_service_details(activity=other_activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT, opportunity_policy=OpportunityPolicy.REQUIRED)
        journey = create_service_journey(service=service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        self.assertIsNone(journey.service_context.opportunity_id)
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        with self.assertRaises(ValidationError):
            start_service_journey(journey=confirmed, actor=self.manager)


class ServiceTemplateTests(ServiceFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_template_cycles_publish_immutability_and_versioning(self):
        template = create_plan_template(service=self.service, actor=self.manager, key="cv", name="CV v1")
        a = add_template_step(template=template, actor=self.manager, title="A", position=10)
        b = add_template_step(template=template, actor=self.manager, title="B", position=20)
        add_template_dependency(step=b, depends_on=a, actor=self.manager)
        with self.assertRaises(ValidationError):
            add_template_dependency(step=a, depends_on=b, actor=self.manager)
        published = publish_plan_template(template=template, actor=self.manager)
        self.assertEqual(published.status, ServicePlanTemplateStatus.PUBLISHED)
        published.name = "Mutation interdite"
        with self.assertRaises(ValidationError):
            published.save()
        a.title = "Mutation interdite"
        with self.assertRaises(ValidationError):
            a.save()
        with self.assertRaises(ValidationError):
            a.delete()
        successor = create_plan_template_version(template=published, actor=self.manager)
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.status, ServicePlanTemplateStatus.DRAFT)
        self.assertEqual(successor.steps.count(), published.steps.count())
        self.assertEqual(successor.steps.filter(dependencies__isnull=False).distinct().count(), published.steps.filter(dependencies__isnull=False).distinct().count())

    def test_materialization_is_snapshot_and_repeated_call_is_idempotent(self):
        template = self.build_published_template()
        journey = self.create_case(template)
        submit_service_journey(journey=journey, actor=self.beneficiary)
        context = journey.service_context
        first = materialize_service_plan(context=context, actor=self.manager)
        second = materialize_service_plan(context=context, actor=self.manager)
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(journey.steps.count(), 3)
        self.assertEqual(ServicePlanMaterialization.objects.filter(context=context).count(), 3)
        context.refresh_from_db()
        self.assertIsNotNone(context.plan_materialized_at)
        successor = create_plan_template_version(template=template, actor=self.manager)
        successor.steps.filter(title="Préparer CV").update(title="Préparer un nouveau CV")
        self.assertTrue(journey.steps.filter(title="Préparer CV").exists())
        self.assertFalse(journey.steps.filter(title="Préparer un nouveau CV").exists())


class ServiceIntakeTests(ServiceFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.template = self.build_published_template()
        self.journey = self.create_case(self.template)

    def question(self, key, kind, *, options=None):
        question = ServiceIntakeQuestion(service=self.service, key=key, prompt=key.replace("-", " "), question_type=kind, options=options or [])
        question.save()
        return question

    def test_all_intake_types_and_strict_validation(self):
        cases = [
            ("short", ServiceIntakeQuestionType.SHORT_TEXT, "Développeur", None),
            ("long", ServiceIntakeQuestionType.LONG_TEXT, "Une description plus longue", None),
            ("bool", ServiceIntakeQuestionType.BOOLEAN, True, None),
            ("date", ServiceIntakeQuestionType.DATE, "2026-09-15", None),
            ("single", ServiceIntakeQuestionType.SINGLE_CHOICE, "junior", ["junior", "senior"]),
            ("multi", ServiceIntakeQuestionType.MULTIPLE_CHOICE, ["fr", "en"], ["fr", "en", "ln"]),
        ]
        for key, kind, value, options in cases:
            question = self.question(key, kind, options=options)
            answer = answer_intake_question(journey=self.journey, question=question, value=value, actor=self.beneficiary)
            self.assertEqual(answer.value, value)
        with self.assertRaises(ValidationError):
            answer_intake_question(journey=self.journey, question=self.question("bad-bool", ServiceIntakeQuestionType.BOOLEAN), value="true", actor=self.beneficiary)
        with self.assertRaises(ValidationError):
            answer_intake_question(journey=self.journey, question=self.question("bad-choice", ServiceIntakeQuestionType.SINGLE_CHOICE, options=["A", "B"]), value="C", actor=self.beneficiary)

    def test_file_is_not_an_intake_answer(self):
        question = self.question("goal", ServiceIntakeQuestionType.SHORT_TEXT)
        with self.assertRaises(ValidationError):
            answer_intake_question(journey=self.journey, question=question, value={"file": "cv.pdf"}, actor=self.beneficiary)

    def test_required_intake_blocks_submission_until_snapshot_exists(self):
        question = self.question("objective", ServiceIntakeQuestionType.SHORT_TEXT)
        with self.assertRaises(ValidationError):
            submit_service_journey(journey=self.journey, actor=self.beneficiary)
        answer_intake_question(journey=self.journey, question=question, value="Refaire mon CV", actor=self.beneficiary)
        submitted = submit_service_journey(journey=self.journey, actor=self.beneficiary)
        self.assertEqual(submitted.status, JourneyStatus.CONFIRMED)
        with self.assertRaises(ValidationError):
            answer_intake_question(journey=submitted, question=question, value="Mutation tardive", actor=self.beneficiary)


class ServiceCvReferenceScenarioTests(ServiceFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_cv_case_end_to_end_and_unauthorized_access(self):
        template = self.build_published_template()
        question = ServiceIntakeQuestion.objects.create(service=self.service, key="objective", prompt="Quel est votre objectif ?", question_type=ServiceIntakeQuestionType.LONG_TEXT)
        journey = self.create_case(template)
        answer_intake_question(journey=journey, question=question, value="Refaire mon CV avec l’aide de Makolo.", actor=self.beneficiary)
        confirmed = submit_service_journey(journey=journey, actor=self.beneficiary)
        self.assertEqual(confirmed.status, JourneyStatus.CONFIRMED)
        started = start_service_journey(journey=confirmed, actor=self.manager)
        self.assertEqual(started.status, JourneyStatus.IN_PROGRESS)
        prep = started.steps.get(title="Clarifier l’objectif")
        document = started.steps.get(title="Préparer CV")
        final = started.steps.get(title="Finaliser le dossier")
        self.assertEqual(prep.status, JourneyStepStatus.READY)
        start_step(step=prep, actor=self.manager)
        complete_step(step=prep, actor=self.manager)
        document.refresh_from_db()
        self.assertEqual(document.status, JourneyStepStatus.READY)
        start_step(step=document, actor=self.manager)
        v1 = create_artifact(journey=started, step=document, uploaded_file=pdf_upload(b"version 1"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV")
        review1 = request_artifact_review(artifact=v1, reviewer=self.reviewer, requested_by=self.manager)
        decide_artifact_review(review=review1, actor=self.reviewer, decision=JourneyArtifactReviewStatus.CHANGES_REQUESTED, comment="Ajouter des résultats mesurables.")
        v2 = create_artifact_version(artifact=v1, uploaded_file=pdf_upload(b"version 2"), uploaded_by=self.beneficiary)
        review2 = request_artifact_review(artifact=v2, reviewer=self.reviewer, requested_by=self.manager)
        decide_artifact_review(review=review2, actor=self.reviewer, decision=JourneyArtifactReviewStatus.APPROVED, comment="Validé.")
        complete_step(step=document, actor=self.manager)
        final.refresh_from_db()
        self.assertEqual(final.status, JourneyStepStatus.READY)
        start_step(step=final, actor=self.manager)
        blocker = create_blocker(journey=started, step=final, actor=self.manager, title="Validation administrative en attente")
        self.assertEqual(blocker.status, JourneyBlockerStatus.ACTIVE)
        resolve_blocker(blocker=blocker, actor=self.manager, resolution_note="Validation reçue")
        complete_step(step=final, actor=self.manager)
        fulfilled = fulfill_service_journey(journey=started, actor=self.manager)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)
        from journeys.collaboration_services import artifact_for_download, notes_for_actor
        with self.assertRaises(PermissionDenied):
            artifact_for_download(actor=self.outsider, artifact_id=v2.pk)
        with self.assertRaises(PermissionDenied):
            list(notes_for_actor(actor=self.outsider, journey=fulfilled))
