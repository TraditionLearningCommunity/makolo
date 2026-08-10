from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole

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
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.event_manager,
            role=OrganizationRole.EVENT_MANAGER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.finance_member,
            role=OrganizationRole.FINANCE,
            is_active=True,
        )
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

    def test_participant_navigation_hides_organizer_and_staff_tools(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_mode"], "participant")
        self.assertContains(response, "Découvrir")
        self.assertContains(response, "Mes billets")
        self.assertNotContains(response, "Mes organisations")
        self.assertNotContains(response, "CRM & audiences")
        self.assertNotContains(response, "Operations Center")
        self.assertNotContains(response, "Contrôle d’accès")

    def test_event_manager_sees_only_relevant_organization_tools(self):
        self.client.force_login(self.event_manager)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_mode"], "organizer")
        self.assertContains(response, "Mes organisations")
        self.assertContains(response, "Billetterie")
        self.assertContains(response, "Espace organisation")
        self.assertNotContains(response, "Paiements réussis")
        self.assertNotContains(response, "CRM & audiences")
        self.assertEqual(response.context["events_count"], 1)

    def test_finance_member_sees_finance_capability_without_marketing_tools(self):
        self.client.force_login(self.finance_member)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_mode"], "organizer")
        self.assertTrue(response.context["web_capabilities"]["can_manage_finance"])
        self.assertContains(response, "Paiements")
        self.assertNotContains(response, "CRM & audiences")

    def test_staff_sees_operations_shortcut(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_mode"], "staff")
        self.assertContains(response, "Operations Center")
        self.assertContains(response, "Pilotage plateforme")

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
