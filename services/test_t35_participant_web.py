from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from groups.models import (
    ActivityGroupEligibility,
    ActivityGroupEligibilityStatus,
    Group,
    GroupMembership,
    GroupMembershipStatus,
)
from opportunities.models import OpportunityKind, OpportunitySourceType
from opportunities.services import create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision, withdraw_opportunity

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
        opportunity.refresh_from_db()
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

    def test_web_start_replays_same_intention_without_creating_another_journey(self):
        self.client.force_login(self.participant)
        url = reverse("services:start", kwargs={"pk": self.none_service.pk})
        first_page = self.client.get(url)
        key = first_page.context["operation_key"]
        self.assertTrue(key)
        payload = {"objective": "Réviser mon CV", "operation_key": key}
        first = self.client.post(url, payload)
        repeated = self.client.post(url, payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(repeated.status_code, 302)
        self.assertEqual(first["Location"], repeated["Location"])
        self.assertEqual(
            self.participant.beneficiary_journeys.filter(
                activity=self.none_service.activity
            ).count(), 1,
        )

        new_page = self.client.get(url)
        new_key = new_page.context["operation_key"]
        self.assertNotEqual(new_key, key)
        self.assertEqual(
            self.client.post(url, {
                "objective": "Nouvelle demande volontaire",
                "operation_key": new_key,
            }).status_code, 302,
        )
        self.assertEqual(
            self.participant.beneficiary_journeys.filter(
                activity=self.none_service.activity
            ).count(), 2,
        )

    def test_web_start_two_open_tabs_have_independent_operation_keys(self):
        self.client.force_login(self.participant)
        url = reverse("services:start", kwargs={"pk": self.none_service.pk})
        first_key = self.client.get(url).context["operation_key"]
        second_key = self.client.get(url).context["operation_key"]
        self.assertNotEqual(first_key, second_key)
        first = self.client.post(url, {
            "operation_key": first_key, "objective": "Premier projet",
        })
        second = self.client.post(url, {
            "operation_key": second_key, "objective": "Deuxième projet",
        })
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertNotEqual(first["Location"], second["Location"])
        self.assertEqual(
            self.participant.beneficiary_journeys.filter(
                activity=self.none_service.activity
            ).count(), 2,
        )

    def test_web_replay_survives_withdrawn_opportunity_and_preserves_revision(self):
        self.client.force_login(self.participant)
        url = reverse("services:start", kwargs={"pk": self.required_service.pk})
        operation_key = self.client.get(url).context["operation_key"]
        payload = {
            "operation_key": operation_key,
            "objective": "Candidater à la bourse",
            "opportunity": str(self.opportunity.pk),
        }
        accepted = self.client.post(url, payload)
        self.assertEqual(accepted.status_code, 302)
        journey = self.participant.beneficiary_journeys.get(
            activity=self.required_service.activity
        )
        original_revision = journey.service_context.opportunity_revision_id
        withdraw_opportunity(opportunity=self.opportunity, actor=self.manager)
        replay = self.client.post(url, payload)
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(replay["Location"], accepted["Location"])
        self.assertEqual(
            self.participant.beneficiary_journeys.filter(
                activity=self.required_service.activity
            ).count(), 1,
        )
        journey.service_context.refresh_from_db()
        self.assertEqual(journey.service_context.opportunity_revision_id, original_revision)

        detail = self.client.get(
            reverse("core:participant-journey-detail", args=[journey.pk])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "L’opportunité n’est plus publiée")
        self.assertNotContains(
            detail, reverse("opportunities:detail", args=[self.opportunity.pk])
        )
        personal_api = self.client.get(f"/api/v1/me/journeys/{journey.pk}/")
        self.assertEqual(personal_api.status_code, 200)
        request_data = personal_api.json()["data"]["service_request"]
        self.assertEqual(request_data["objective"], payload["objective"])
        self.assertEqual(request_data["opportunity"]["title"], "Emploi fictif")
        self.assertEqual(request_data["opportunity"]["publication_state"], "withdrawn")

    def test_web_start_rejects_reused_key_with_changed_payload(self):
        self.client.force_login(self.participant)
        url = reverse("services:start", kwargs={"pk": self.none_service.pk})
        key = self.client.get(url).context["operation_key"]
        self.assertEqual(
            self.client.post(url, {
                "operation_key": key, "objective": "Première demande",
            }).status_code, 302,
        )
        changed = self.client.post(url, {
            "operation_key": key, "objective": "Demande altérée",
        })
        self.assertEqual(changed.status_code, 200)
        self.assertContains(changed, "déjà été utilisée pour une autre demande")
        self.assertEqual(
            self.participant.beneficiary_journeys.filter(
                activity=self.none_service.activity
            ).count(), 1,
        )

    def test_direct_web_service_start_respects_group_eligibility(self):
        self.client.force_login(self.participant)
        group = Group.objects.create(
            name="Service réservé",
            owner_profile=self.manager,
            created_by=self.manager,
        )
        ActivityGroupEligibility.objects.create(
            group=group,
            activity=self.none_service.activity,
            status=ActivityGroupEligibilityStatus.APPROVED,
            requested_by=self.manager,
            decided_by=self.manager,
            decided_at=timezone.now(),
        )
        url = reverse("services:start", kwargs={"pk": self.none_service.pk})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(url, {"objective": "Tentative non autorisée"}).status_code,
            404,
        )
        self.assertFalse(
            self.participant.beneficiary_journeys.filter(
                activity=self.none_service.activity
            ).exists()
        )
        GroupMembership.objects.create(
            group=group,
            profile=self.participant,
            status=GroupMembershipStatus.ACTIVE,
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.post(url, {"objective": "Demande admissible"}).status_code,
            302,
        )

    def test_participant_cannot_open_another_users_intake(self):
        self.client.force_login(self.participant)
        self.client.post(reverse("services:start", kwargs={"pk": self.none_service.pk}), {"objective": "CV"})
        journey = self.participant.beneficiary_journeys.get(activity=self.none_service.activity)
        other = User.objects.create_user(username="t35-intake-other", email="other@example.test", password="x")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("services:intake", kwargs={"pk": journey.pk})).status_code, 404)
