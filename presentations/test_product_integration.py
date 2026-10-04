from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from activities.models import ActivityVisibility
from activities.services import create_activity, create_occurrence
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey
from organizations.services import create_organization

from .catalog import ensure_builtin_catalog
from .enums import PresentationPurpose, Provenance, VersionStatus, Visibility
from .library_services import activate_template_version, duplicate_template, set_space_default
from .models import ActivityPresentation, PresentationTemplate, PresentationTemplateVersion
from .product_usage import access_presentation_purpose
from .services import configure_activity_presentation, publish_activity_presentation


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

    def test_activation_keeps_personal_template_private(self):
        template, version = duplicate_template(
            actor=self.owner,
            source_version=self.templates["formal"],
            slug="private-pr3-copy",
            name="Private PR3 Copy",
        )
        activate_template_version(actor=self.owner, version=version)
        template.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(template.visibility, Visibility.PRIVATE)
        self.assertEqual(version.status, VersionStatus.PUBLISHED)

    def test_forged_incompatible_template_selection_is_rejected(self):
        manifest = dict(self.templates["formal"].manifest)
        manifest["purposes"] = [PresentationPurpose.PUBLIC_PAGE]
        template = PresentationTemplate.objects.create(
            slug="pr3-public-only",
            name="PR3 Public Only",
            provenance=Provenance.USER,
            visibility=Visibility.PRIVATE,
            owner_profile=self.owner,
            created_by=self.owner,
        )
        version = PresentationTemplateVersion.objects.create(
            template=template,
            version_number=1,
            status=VersionStatus.PUBLISHED,
            schema_version=1,
            manifest=manifest,
            created_by=self.owner,
        )
        with self.assertRaisesMessage(ValidationError, "compatible"):
            configure_activity_presentation(
                actor=self.owner,
                activity=self.activity,
                purpose=PresentationPurpose.INVITATION,
                template_version=version,
                theme_version=self.themes["makolo-violet"],
            )

    def test_private_public_page_studio_does_not_offer_dead_public_link(self):
        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save(update_fields=["visibility", "updated_at"])
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("presentations:studio", kwargs={"activity_id": self.activity.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ouvrir la page présentée")
        self.assertContains(response, "ne devient publique")

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


    def test_studio_can_return_to_space_default_without_copying_it(self):
        space = create_organization(creator=self.owner, name="PR3 Default Space")
        activity = create_activity(
            space=space,
            created_by=self.owner,
            title="PR3 Default Activity",
        )
        set_space_default(
            actor=self.owner,
            space=space,
            purpose=PresentationPurpose.PUBLIC_PAGE,
            template_version=self.templates["formal"],
            theme_version=self.themes["ivory"],
        )
        binding = configure_activity_presentation(
            actor=self.owner,
            activity=activity,
            purpose=PresentationPurpose.PUBLIC_PAGE,
            template_version=self.templates["professional"],
            theme_version=self.themes["makolo-ink"],
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
        occurrence = create_occurrence(activity=self.activity)
        binding = configure_activity_presentation(
            actor=self.owner,
            activity=self.activity,
            occurrence=occurrence,
            purpose=PresentationPurpose.INVITATION,
            template_version=self.templates["formal"],
            theme_version=self.themes["ivory"],
            editorial_data={"invitation_message": "Vous êtes invité."},
        )
        publish_activity_presentation(actor=self.owner, presentation=binding)
        journey = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=occurrence,
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
        self.assertContains(response, "PR3 Activity")
        self.assertEqual(response["Cache-Control"], "private, no-store")

        self.client.force_login(self.other)
        hidden = self.client.get(
            reverse(
                "presentations:participant-invitation",
                kwargs={"journey_id": journey.pk},
            )
        )
        self.assertEqual(hidden.status_code, 404)
