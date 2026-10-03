from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from access.services import issue_access, render_access_credential
from activities.models import ActivityVisibility
from activities.services import create_activity, create_occurrence
from organizations.services import create_organization

from .catalog import ensure_builtin_catalog
from .enums import PresentationPurpose
from .services import configure_activity_presentation, publish_activity_presentation


User = get_user_model()


from django.test import TestCase


class MPSMobileAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="mps-mobile-owner",
            email="mps-mobile-owner@example.test",
            password="StrongPass2026!",
        )
        self.participant = User.objects.create_user(
            username="mps-mobile-participant",
            email="mps-mobile-participant@example.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="mps-mobile-outsider",
            email="mps-mobile-outsider@example.test",
            password="StrongPass2026!",
        )
        self.space = create_organization(creator=self.owner, name="MPS Mobile Space")
        self.activity = create_activity(
            space=self.space,
            created_by=self.owner,
            title="MPS Mobile Activity",
        )
        self.activity.visibility = ActivityVisibility.PUBLIC
        self.activity.save(update_fields=["visibility", "updated_at"])
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            timezone="Africa/Lubumbashi",
        )
        self.templates, self.themes = ensure_builtin_catalog(actor=self.owner)

    def _publish_access_presentation(self):
        presentation = configure_activity_presentation(
            actor=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            purpose=PresentationPurpose.ACCESS_PASS,
            template_version=self.templates["professional"],
            theme_version=self.themes["makolo-ink"],
        )
        publish_activity_presentation(actor=self.owner, presentation=presentation)
        return presentation

    def test_access_artifact_is_compact_and_keeps_credential_out_of_snapshot(self):
        presentation = self._publish_access_presentation()
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            issued_by=self.owner,
            valid_from=timezone.now() - timedelta(minutes=5),
            valid_until=timezone.now() + timedelta(hours=4),
        )
        credential = access.credentials.get()
        raw = render_access_credential(credential)

        self.client.force_authenticate(self.participant)
        response = self.client.get(
            reverse("presentations-api:access-artifact", kwargs={"pk": access.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["purpose"], PresentationPurpose.ACCESS_PASS)
        self.assertEqual(data["template"]["resource_key"], str(presentation.template_version_id))
        self.assertEqual(data["theme"]["resource_key"], str(presentation.theme_version_id))
        self.assertEqual(data["capabilities"], ["open_credential"])
        self.assertIn("credential", data["links"])
        self.assertNotIn(raw, response.content.decode("utf-8"))
        self.assertNotIn("manifest", data)
        self.assertNotIn("tokens", data)

    def test_template_and_theme_are_fetched_as_separate_immutable_projections(self):
        presentation = self._publish_access_presentation()
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            issued_by=self.owner,
        )
        self.client.force_authenticate(self.participant)

        artifact = self.client.get(
            reverse("presentations-api:access-artifact", kwargs={"pk": access.pk})
        ).json()["data"]

        template_response = self.client.get(artifact["template"]["path"])
        theme_response = self.client.get(artifact["theme"]["path"])
        self.assertEqual(template_response.status_code, 200)
        self.assertEqual(theme_response.status_code, 200)
        self.assertEqual(
            template_response.json()["meta"]["projection"],
            "mps.template.version",
        )
        self.assertEqual(
            theme_response.json()["meta"]["projection"],
            "mps.theme.version",
        )
        self.assertEqual(
            template_response.json()["data"]["manifest"],
            presentation.template_version.manifest,
        )
        self.assertEqual(
            theme_response.json()["data"]["tokens"],
            presentation.theme_version.tokens,
        )
        self.assertIn("immutable", template_response["Cache-Control"])
        self.assertIn("immutable", theme_response["Cache-Control"])

    def test_default_artifact_uses_builtin_essential_without_definition_round_trip(self):
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            issued_by=self.owner,
        )
        self.client.force_authenticate(self.participant)
        response = self.client.get(
            reverse("presentations-api:access-artifact", kwargs={"pk": access.pk})
        )
        data = response.json()["data"]
        self.assertTrue(data["template"]["builtin"])
        self.assertTrue(data["theme"]["builtin"])
        self.assertEqual(data["fallback_reason"], "makolo-essential")
        self.assertNotIn("path", data["template"])
        self.assertNotIn("path", data["theme"])

    def test_outsider_cannot_read_another_profiles_access_presentation(self):
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            issued_by=self.owner,
        )
        self.client.force_authenticate(self.outsider)
        response = self.client.get(
            reverse("presentations-api:access-artifact", kwargs={"pk": access.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_public_activity_presentation_is_available_but_private_one_is_not(self):
        self.client.force_authenticate(self.outsider)
        public_response = self.client.get(
            reverse(
                "presentations-api:activity-artifact",
                kwargs={"pk": self.activity.pk, "purpose": PresentationPurpose.PUBLIC_PAGE},
            )
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.json()["meta"]["scope"], "activity")

        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save(update_fields=["visibility", "updated_at"])
        private_response = self.client.get(
            reverse(
                "presentations-api:activity-artifact",
                kwargs={"pk": self.activity.pk, "purpose": PresentationPurpose.PUBLIC_PAGE},
            )
        )
        self.assertEqual(private_response.status_code, 404)
