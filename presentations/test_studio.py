from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import AccessUseResult
from access.services import issue_access, render_access_credential, validate_access_credential
from activities.models import ActivityVisibility
from activities.services import create_activity, create_occurrence
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey
from organizations.services import create_organization

from .catalog import catalog_entries, ensure_builtin_catalog
from .enums import PresentationPurpose
from .library_services import activate_owned_template_version, duplicate_template, set_space_default
from .models import ActivityPresentation
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

    def test_studio_selects_published_personal_library_version(self):
        templates, themes = ensure_builtin_catalog(actor=self.owner)
        _, version = duplicate_template(
            actor=self.owner,
            source_version=templates["formal"],
            slug="my-formal",
            name="My Formal",
        )
        activate_owned_template_version(actor=self.owner, version=version)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("presentations:studio", kwargs={"activity_id": self.activity.pk}),
            {
                "purpose": PresentationPurpose.INVITATION,
                "template_version": str(version.pk),
                "theme_version": str(themes["ivory"].pk),
                "action": "publish",
            },
        )
        self.assertEqual(response.status_code, 302)
        binding = ActivityPresentation.objects.get(
            activity=self.activity,
            purpose=PresentationPurpose.INVITATION,
        )
        self.assertEqual(binding.template_version_id, version.pk)
        self.assertEqual(binding.theme_version_id, themes["ivory"].pk)

    def test_studio_can_return_to_space_default_without_copying_it(self):
        space = create_organization(creator=self.owner, name="Studio Default Space")
        activity = create_activity(
            space=space,
            created_by=self.owner,
            title="Studio Default Activity",
        )
        templates, themes = ensure_builtin_catalog(actor=self.owner)
        set_space_default(
            actor=self.owner,
            space=space,
            purpose=PresentationPurpose.PUBLIC_PAGE,
            template_version=templates["formal"],
            theme_version=themes["ivory"],
        )
        binding = configure_activity_presentation(
            actor=self.owner,
            activity=activity,
            purpose=PresentationPurpose.PUBLIC_PAGE,
            template_version=templates["professional"],
            theme_version=themes["makolo-ink"],
        )
        publish_activity_presentation(actor=self.owner, presentation=binding)

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("presentations:studio", kwargs={"activity_id": activity.pk}),
            {
                "purpose": PresentationPurpose.PUBLIC_PAGE,
                "action": "use_default",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ActivityPresentation.objects.filter(
                activity=activity,
                purpose=PresentationPurpose.PUBLIC_PAGE,
            ).exists()
        )

    def test_participant_invitation_is_private_and_uses_activity_presentation(self):
        templates, themes = ensure_builtin_catalog(actor=self.owner)
        binding = configure_activity_presentation(
            actor=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            purpose=PresentationPurpose.INVITATION,
            template_version=templates["formal"],
            theme_version=themes["ivory"],
            editorial_data={"invitation_message": "Vous êtes invité."},
        )
        publish_activity_presentation(actor=self.owner, presentation=binding)
        journey = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.INVITATION,
            status=JourneyStatus.SUBMITTED,
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "presentations:participant-invitation",
                kwargs={"journey_id": journey.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Studio")
        self.assertEqual(response["Cache-Control"], "private, no-store")

        self.client.force_login(self.other)
        hidden = self.client.get(
            reverse(
                "presentations:participant-invitation",
                kwargs={"journey_id": journey.pk},
            )
        )
        self.assertEqual(hidden.status_code, 404)

