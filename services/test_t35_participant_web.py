from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from opportunities.models import OpportunityKind, OpportunitySourceType
from opportunities.services import create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision

from .models import OpportunityPolicy, ServiceIntakeQuestion, ServiceIntakeQuestionType, ServiceKind
from .services import add_template_step, create_plan_template, create_service_details, publish_plan_template


User = get_user_model()


class ServiceParticipantWebTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser(username="t35-service-manager", email="t35-manager@example.test", password="x")
        self.participant = User.objects.create_user(username="t35-service-participant", email="t35-participant@example.test", password="x")
        self.none_service = self._service("Refaire mon CV", OpportunityPolicy.NONE)
        self.required_service = self._service("Candidature accompagnée", OpportunityPolicy.REQUIRED)
        self.opportunity = self._opportunity("Emploi fictif")

    def _service(self, title, policy):
        activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title=title, short_description="Accompagnement de démonstration", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        service = create_service_details(activity=activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT, opportunity_policy=policy)
        template = create_plan_template(service=service, actor=self.manager, key="default", name="Plan standard")
        add_template_step(template=template, actor=self.manager, title="Préparer le dossier", position=10)
        publish_plan_template(template=template, actor=self.manager)
        ServiceIntakeQuestion.objects.create(service=service, key="goal", prompt="Quel est votre objectif ?", question_type=ServiceIntakeQuestionType.SHORT_TEXT, is_required=True, position=10)
        return service

    def _opportunity(self, title):
        opportunity = create_opportunity(actor=self.manager, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.manager, title=title, issuer_name="Entreprise fictive")
        create_opportunity_source(opportunity=opportunity, actor=self.manager, source_type=OpportunitySourceType.OFFICIAL, source_name="Source fictive", url=f"https://example.test/{opportunity.pk}", is_primary=True, verified=True)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.manager)
        return opportunity

    def test_catalog_is_public_and_only_lists_published_public_services(self):
        response = self.client.get(reverse("services:list"))
        self.assertContains(response, "Refaire mon CV")
        self.assertContains(response, "Candidature accompagnée")
        hidden = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Service privé", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PRIVATE)
        create_service_details(activity=hidden, actor=self.manager, service_kind=ServiceKind.OTHER)
        self.assertNotContains(self.client.get(reverse("services:list")), "Service privé")

    def test_service_without_opportunity_creates_draft_then_validates_intake_server_side(self):
        self.client.force_login(self.participant)
        response = self.client.post(reverse("services:start", kwargs={"pk": self.none_service.pk}), {"objective": "Améliorer mon CV"})
        self.assertEqual(response.status_code, 302)
        journey = self.participant.beneficiary_journeys.get(activity=self.none_service.activity)
        self.assertIsNone(journey.service_context.opportunity_id)
        intake_url = reverse("services:intake", kwargs={"pk": journey.pk})
        response = self.client.post(intake_url, {"action": "submit"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cette réponse est obligatoire")
        response = self.client.post(intake_url, {f"question_{self.none_service.intake_questions.get().pk}": "Obtenir un CV clair", "action": "submit"})
        self.assertEqual(response.status_code, 302)
        journey.refresh_from_db()
        self.assertNotEqual(journey.status, "draft")

    def test_required_opportunity_cannot_be_omitted_and_revision_is_pinned(self):
        self.client.force_login(self.participant)
        url = reverse("services:start", kwargs={"pk": self.required_service.pk})
        response = self.client.post(url, {"objective": "Candidater"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ce champ est obligatoire")
        response = self.client.post(url, {"objective": "Candidater", "opportunity": str(self.opportunity.pk)})
        self.assertEqual(response.status_code, 302)
        journey = self.participant.beneficiary_journeys.get(activity=self.required_service.activity)
        self.assertEqual(journey.service_context.opportunity_id, self.opportunity.pk)
        self.assertEqual(journey.service_context.opportunity_revision_id, self.opportunity.current_revision_id)

    def test_participant_cannot_open_another_users_intake(self):
        self.client.force_login(self.participant)
        self.client.post(reverse("services:start", kwargs={"pk": self.none_service.pk}), {"objective": "CV"})
        journey = self.participant.beneficiary_journeys.get(activity=self.none_service.activity)
        other = User.objects.create_user(username="t35-intake-other", email="other@example.test", password="x")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("services:intake", kwargs={"pk": journey.pk})).status_code, 404)
