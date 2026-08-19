from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authorization.services import ensure_platform_admin_mandate
from events.models import Event, EventStatus, EventVisibility
from organizations.services import create_organization


User = get_user_model()

MANIFEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


@override_settings(STORAGES=MANIFEST_STORAGES, WHITENOISE_MANIFEST_STRICT=True)
class ProductionManifestPageSmokeTests(TestCase):
    def setUp(self):
        self.participant = User.objects.create_user(username="manifest-participant", email="manifest-participant@example.com", password="Strong-manifest-participant-2026!")
        self.organizer = User.objects.create_user(username="manifest-organizer", email="manifest-organizer@example.com", password="Strong-manifest-organizer-2026!")
        self.staff = User.objects.create_user(username="manifest-staff", email="manifest-staff@example.com", password="Strong-manifest-staff-2026!", is_staff=True)
        ensure_platform_admin_mandate(profile=self.staff, source="test-fixture")
        self.organization = create_organization(creator=self.organizer, name="Manifest Smoke Organization")
        start_at = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(organizer=self.organizer, organization=self.organization, title="Manifest Smoke Event", status=EventStatus.PUBLISHED, visibility=EventVisibility.PUBLIC, start_at=start_at, end_at=start_at + timedelta(hours=3), published_at=timezone.now())

    def assert_page_renders(self, url, *, user=None):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:500])
        return response

    def test_public_home_login_and_discovery_render(self):
        self.assert_page_renders(reverse("core:home"))
        self.assert_page_renders(reverse("core:login"))
        self.assert_page_renders(reverse("discovery:home"))

    def test_participant_personal_pages_render(self):
        self.assert_page_renders(reverse("core:participant-home"), user=self.participant)
        self.assert_page_renders(reverse("core:participant-journeys"), user=self.participant)
        self.assert_page_renders(reverse("core:participant-accesses"), user=self.participant)
        self.assert_page_renders(reverse("account:profile"), user=self.participant)

    def test_space_console_overview_renders_for_owner(self):
        self.assert_page_renders(reverse("organizations:console-overview", kwargs={"slug": self.organization.slug}), user=self.organizer)

    def test_scanner_and_operations_render_for_staff(self):
        scanner = self.assert_page_renders(reverse("scanner:console", kwargs={"slug": self.event.slug}), user=self.staff)
        self.assertContains(scanner, "dist/scanner")
        self.assert_page_renders(reverse("operations:dashboard"), user=self.staff)
