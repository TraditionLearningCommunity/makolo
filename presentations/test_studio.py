from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import AccessUseResult
from access.services import issue_access, render_access_credential, validate_access_credential
from activities.models import ActivityVisibility
from activities.services import create_activity, create_occurrence

from .catalog import catalog_entries, ensure_builtin_catalog
from .enums import PresentationPurpose
from .services import configure_activity_presentation, publish_activity_presentation

User = get_user_model()


class PresentationStudioTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="m3b-owner", email="m3b-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="m3b-other", email="m3b-other@example.test", password="StrongPass2026!")
        self.activity = create_activity(owner_profile=self.owner, created_by=self.owner, title="Makolo Studio")
        self.activity.visibility = ActivityVisibility.PUBLIC
        self.activity.save(update_fields=["visibility", "updated_at"])
        self.occurrence = create_occurrence(activity=self.activity, start_at=timezone.now() + timedelta(hours=2), timezone="Africa/Lubumbashi")

    def test_catalog_has_eight_templates_and_seven_themes(self):
        templates, themes = ensure_builtin_catalog(actor=self.owner)
        self.assertEqual(len(catalog_entries()), 8)
        self.assertEqual(len(templates), 8)
        self.assertEqual(len(themes), 7)

    def test_studio_requires_activity_manage_authority(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("presentations:studio", kwargs={"activity_id": self.activity.pk}))
        self.assertEqual(response.status_code, 403)

    def test_studio_preview_uses_real_activity_data(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("presentations:preview", kwargs={"activity_id": self.activity.pk}) + "?mode=phone")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Studio")
        self.assertContains(response, "mps-preview-frame-phone")

    def test_public_activity_without_configuration_uses_essential(self):
        response = self.client.get(reverse("presentations:public-activity", kwargs={"activity_id": self.activity.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Studio")
        self.assertContains(response, "mps-mark")

    def test_alternative_access_template_renders_canonical_qr_and_scans(self):
        templates, themes = ensure_builtin_catalog(actor=self.owner)
        presentation = configure_activity_presentation(
            actor=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            purpose=PresentationPurpose.ACCESS_PASS,
            template_version=templates["professional"],
            theme_version=themes["makolo-ink"],
        )
        publish_activity_presentation(actor=self.owner, presentation=presentation)
        access = issue_access(beneficiary=self.owner, activity=self.activity, occurrence=self.occurrence, issued_by=self.owner, valid_from=timezone.now() - timedelta(minutes=5), valid_until=timezone.now() + timedelta(hours=4))
        credential = access.credentials.get()
        token = render_access_credential(credential)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("presentations:participant-access", kwargs={"access_id": access.pk}))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("data:image/png;base64,", html)
        self.assertNotIn(token, html)
        outcome = validate_access_credential(token, expected_activity=self.activity, expected_occurrence=self.occurrence)
        self.assertEqual(outcome.result, AccessUseResult.ACCEPTED)

    def test_print_surface_hides_interactive_cta_by_contract(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("presentations:preview", kwargs={"activity_id": self.activity.pk}) + "?mode=print")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mps-preview-print")
        self.assertContains(response, "presentations/mps.css")
