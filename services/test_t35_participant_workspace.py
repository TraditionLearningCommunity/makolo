from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.collaboration_models import JourneyNote, JourneyNoteVisibility

from .models import ServiceKind
from .services import create_service_details, create_service_journey


User = get_user_model()


class ServiceParticipantWorkspaceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser(username="t35-workspace-manager", email="workspace-manager@example.test", password="x")
        self.participant = User.objects.create_user(username="t35-workspace-participant", email="workspace-participant@example.test", password="x")
        self.other = User.objects.create_user(username="t35-workspace-other", email="workspace-other@example.test", password="x")
        activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Aide CV workspace", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        self.service = create_service_details(activity=activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.participant, beneficiary=self.participant, objective="Refaire mon CV")
        JourneyNote.objects.create(journey=self.journey, author=self.manager, visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE, body="Visible au bénéficiaire")
        JourneyNote.objects.create(journey=self.journey, author=self.manager, visibility=JourneyNoteVisibility.INTERNAL, body="Secret interne opérateur")

    def test_service_journey_uses_services_workspace_and_server_filters_internal_notes(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Démarche Services")
        self.assertContains(response, "Refaire mon CV")
        self.assertContains(response, "Visible au bénéficiaire")
        self.assertNotContains(response, "Secret interne opérateur")

    def test_foreign_participant_still_cannot_load_services_workspace(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        self.assertEqual(response.status_code, 404)
