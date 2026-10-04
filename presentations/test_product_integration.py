from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from activities.models import ActivityVisibility
from activities.services import create_activity
from journeys.models import WorkflowKind

from .catalog import ensure_builtin_catalog
from .enums import PresentationPurpose
from .library_services import activate_template_version, duplicate_template
from .product_usage import access_presentation_purpose


User = get_user_model()


class MPSProductPurposeTests(SimpleTestCase):
    def test_registration_access_uses_confirmation_purpose(self):
        access = SimpleNamespace(
            activity=SimpleNamespace(),
            journey=SimpleNamespace(workflow=WorkflowKind.REGISTRATION),
        )
        self.assertEqual(
            access_presentation_purpose(access),
            PresentationPurpose.CONFIRMATION,
        )

    def test_invitation_access_uses_invitation_purpose(self):
        access = SimpleNamespace(
            activity=SimpleNamespace(),
            journey=SimpleNamespace(workflow=WorkflowKind.INVITATION),
        )
        self.assertEqual(
            access_presentation_purpose(access),
            PresentationPurpose.INVITATION,
        )

    def test_plain_access_keeps_access_pass_purpose(self):
        access = SimpleNamespace(activity=SimpleNamespace(), journey=None)
        self.assertEqual(
            access_presentation_purpose(access),
            PresentationPurpose.ACCESS_PASS,
        )


class MPSProductIntegrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mps-pr3-owner",
            email="mps-pr3-owner@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="mps-pr3-other",
            email="mps-pr3-other@example.test",
            password="StrongPass2026!",
        )
        self.activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="PR3 Activity",
        )
        self.activity.visibility = ActivityVisibility.PUBLIC
        self.activity.save(update_fields=["visibility", "updated_at"])
        self.templates, self.themes = ensure_builtin_catalog(actor=self.owner)

    def test_personal_duplicate_can_be_activated_and_selected_in_studio(self):
        _, version = duplicate_template(
            actor=self.owner,
            source_version=self.templates["formal"],
            slug="formal-pr3-copy",
            name="Formal PR3 Copy",
        )
        activate_template_version(actor=self.owner, version=version)

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("presentations:studio", kwargs={"activity_id": self.activity.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formal PR3 Copy")
        self.assertContains(response, f'value="{version.pk}"')

    def test_public_invitation_and_program_outputs_are_real_surfaces(self):
        for purpose in (PresentationPurpose.INVITATION, PresentationPurpose.PROGRAM):
            response = self.client.get(
                reverse(
                    "presentations:activity-artifact",
                    kwargs={"activity_id": self.activity.pk, "purpose": purpose},
                )
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "PR3 Activity")

    def test_badge_is_not_exposed_as_generic_activity_artifact(self):
        response = self.client.get(
            reverse(
                "presentations:activity-artifact",
                kwargs={
                    "activity_id": self.activity.pk,
                    "purpose": PresentationPurpose.BADGE,
                },
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_private_activity_artifact_requires_manage_authority(self):
        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save(update_fields=["visibility", "updated_at"])
        url = reverse(
            "presentations:activity-artifact",
            kwargs={
                "activity_id": self.activity.pk,
                "purpose": PresentationPurpose.PROGRAM,
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
