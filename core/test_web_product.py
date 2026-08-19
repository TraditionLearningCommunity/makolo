from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authorization.constants import SystemRoleCode
from authorization.services import ensure_platform_admin_mandate, grant_space_role
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization

from .error_views import error_500


User = get_user_model()


@override_settings(DEBUG=False)
class RoleAwareWebProductTests(TestCase):
    def setUp(self):
        self.participant = User.objects.create_user(
            username="participant-web",
            email="participant-web@example.com",
            password="Strong-participant-web-2026!",
        )
        self.event_manager = User.objects.create_user(
            username="event-manager-web",
            email="event-manager-web@example.com",
            password="Strong-event-manager-web-2026!",
        )
        self.finance_member = User.objects.create_user(
            username="finance-web",
            email="finance-web@example.com",
            password="Strong-finance-web-2026!",
        )
        self.staff = User.objects.create_user(
            username="staff-web",
            email="staff-web@example.com",
            password="Strong-staff-web-2026!",
            is_staff=True,
        )
        self.organization = Organization.objects.create(
            name="Role UX Organization",
            created_by=self.event_manager,
        )
        grant_space_role(profile=self.event_manager, space=self.organization, role=SystemRoleCode.ACTIVITY_MANAGER)
        grant_space_role(profile=self.finance_member, space=self.organization, role=SystemRoleCode.FINANCE)
        ensure_platform_admin_mandate(profile=self.staff, source="test-fixture")
        start_at = timezone.now() + timedelta(days=5)
        self.event = Event.objects.create(
            organizer=self.event_manager,
            organization=self.organization,
            title="Role UX Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=3),
        )

    def test_participant_navigation_is_personal_and_hides_professional_tools(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accueil")
        self.assertContains(response, "Mes démarches")
        self.assertContains(response, "Mes accès")
        self.assertContains(response, "Notifications")
        self.assertContains(response, "Profil")
        self.assertNotContains(response, "CRM")
        self.assertNotContains(response, "Contrôle d’accès")

    def test_activity_manager_lands_in_space_console_with_activity_tools(self):
        self.client.force_login(self.event_manager)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.organization.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activités")
        self.assertContains(response, "Demandes")
        self.assertContains(response, "Accès")
        self.assertContains(response, "Commandes")
        self.assertContains(response, "Analyses")
        self.assertNotContains(response, ">Paiements<")
        self.assertNotContains(response, ">CRM<")

    def test_finance_member_sees_finance_without_crm_or_activity_management(self):
        self.client.force_login(self.finance_member)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.organization.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commandes")
        self.assertContains(response, "Paiements")
        self.assertContains(response, "Analyses")
        self.assertNotContains(response, ">CRM<")
        self.assertNotContains(response, ">Activités<")
        self.assertNotContains(response, ">Équipe<")

    def test_staff_lands_in_operations(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(response, reverse("operations:dashboard"), fetch_redirect_response=False)

    def test_participant_is_still_refused_server_side_on_event_create(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("events:create"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Erreur 403", status_code=403)

    def test_product_404_page(self):
        response = self.client.get("/page-qui-n-existe-pas-makolo/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Erreur 404", status_code=404)
        self.assertContains(response, "Découvrir", status_code=404)

    def test_product_500_page_exposes_only_correlation_identifier(self):
        request = RequestFactory().get("/synthetic-server-error/")
        request.user = AnonymousUser()

        response = error_500(request)
        body = response.content.decode()

        self.assertEqual(response.status_code, 500)
        self.assertIn("Erreur 500", body)
        self.assertRegex(body, r"MKL-[0-9A-F]{6}")
        self.assertNotIn("Traceback", body)
