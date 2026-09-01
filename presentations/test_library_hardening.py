from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.services import create_activity
from events.models import Event
from organizations.services import create_organization
from transport.models import TransportRoute, TransportService

from .catalog import ensure_builtin_catalog
from .contexts import build_activity_context
from .enums import PresentationPurpose, PresentationState, Provenance, VersionStatus, Visibility
from .essential import ESSENTIAL_MANIFEST
from .library_services import duplicate_template, publish_template_version, set_space_default, submit_template_version, upgrade_presentation
from .models import ActivityPresentation, PresentationTemplate, PresentationTemplateVersion
from .rendering import render_presentation
from .resolver import resolve_presentation
from .services import configure_activity_presentation, publish_activity_presentation

User = get_user_model()


class PresentationLibraryHardeningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="m3c-owner", email="m3c-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="m3c-other", email="m3c-other@example.test", password="StrongPass2026!")
        self.staff = User.objects.create_user(username="m3c-staff", email="m3c-staff@example.test", password="StrongPass2026!", is_staff=True)
        self.space = create_organization(creator=self.owner, name="M3C Space")
        self.other_space = create_organization(creator=self.other, name="Other Space")
        self.activity = create_activity(space=self.space, created_by=self.owner, title="M3C Activity")
        self.templates, self.themes = ensure_builtin_catalog(actor=self.owner)

    def test_space_default_resolves_after_activity_override_layer(self):
        default = set_space_default(actor=self.owner, space=self.space, purpose=PresentationPurpose.INVITATION, template_version=self.templates["formal"], theme_version=self.themes["ivory"])
        resolved = resolve_presentation(activity=self.activity, purpose=PresentationPurpose.INVITATION)
        self.assertEqual(resolved.fallback_reason, "space-default")
        self.assertEqual(resolved.manifest, default.template_version.manifest)
        binding = configure_activity_presentation(actor=self.owner, activity=self.activity, purpose=PresentationPurpose.INVITATION, template_version=self.templates["professional"], theme_version=self.themes["makolo-ink"])
        publish_activity_presentation(actor=self.owner, presentation=binding)
        resolved = resolve_presentation(activity=self.activity, purpose=PresentationPurpose.INVITATION)
        self.assertEqual(resolved.binding.pk, binding.pk)

    def test_space_default_rejects_private_template_from_other_owner(self):
        private = PresentationTemplate.objects.create(slug="private-other", name="Private Other", provenance=Provenance.USER, visibility=Visibility.PRIVATE, owner_profile=self.other, created_by=self.other)
        version = PresentationTemplateVersion.objects.create(template=private, version_number=1, status=VersionStatus.PUBLISHED, manifest=ESSENTIAL_MANIFEST, created_by=self.other)
        with self.assertRaises(PermissionDenied):
            set_space_default(actor=self.owner, space=self.space, purpose=PresentationPurpose.PUBLIC_PAGE, template_version=version, theme_version=self.themes["makolo-violet"])

    def test_duplicate_keeps_provenance_and_does_not_mutate_public_template(self):
        source = self.templates["formal"]
        template, version = duplicate_template(actor=self.owner, source_version=source, slug="formal-copy", name="Formal Copy")
        self.assertEqual(template.provenance, Provenance.USER)
        self.assertEqual(template.owner_profile, self.owner)
        self.assertEqual(version.status, VersionStatus.DRAFT)
        self.assertEqual(source.template.provenance, Provenance.MAKOLO)

    def test_non_staff_cannot_publish_community_template(self):
        _, version = duplicate_template(actor=self.owner, source_version=self.templates["formal"], slug="community-formal", name="Community Formal")
        submit_template_version(actor=self.owner, version=version)
        with self.assertRaises(PermissionDenied):
            publish_template_version(actor=self.owner, version=version)
        publish_template_version(actor=self.staff, version=version)
        version.refresh_from_db()
        version.template.refresh_from_db()
        self.assertEqual(version.status, VersionStatus.PUBLISHED)
        self.assertEqual(version.template.visibility, Visibility.PUBLIC)

    def test_private_other_template_preview_is_forbidden(self):
        private = PresentationTemplate.objects.create(slug="private-preview", name="Private", provenance=Provenance.USER, visibility=Visibility.PRIVATE, owner_profile=self.other, created_by=self.other)
        version = PresentationTemplateVersion.objects.create(template=private, version_number=1, status=VersionStatus.DRAFT, manifest=ESSENTIAL_MANIFEST, created_by=self.other)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("presentations:template-preview", kwargs={"version_id": version.pk}))
        self.assertEqual(response.status_code, 403)

    def test_suspended_pin_falls_back_but_retired_pin_remains_renderable(self):
        binding = configure_activity_presentation(actor=self.owner, activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE, template_version=self.templates["professional"], theme_version=self.themes["makolo-violet"])
        publish_activity_presentation(actor=self.owner, presentation=binding)
        binding.template_version.status = VersionStatus.RETIRED
        binding.template_version.save(update_fields=["status"])
        retired = resolve_presentation(activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        self.assertEqual(retired.binding.pk, binding.pk)
        binding.template_version.status = VersionStatus.SUSPENDED
        binding.template_version.save(update_fields=["status"])
        suspended = resolve_presentation(activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        self.assertIsNone(suspended.binding)
        self.assertEqual(suspended.fallback_reason, "makolo-essential")

    def test_upgrade_is_explicit_and_rejects_other_private_version(self):
        binding = configure_activity_presentation(actor=self.owner, activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE, template_version=self.templates["makolo-essential"], theme_version=self.themes["makolo-violet"])
        publish_activity_presentation(actor=self.owner, presentation=binding)
        old_id = binding.template_version_id
        private = PresentationTemplate.objects.create(slug="upgrade-other", name="Upgrade Other", provenance=Provenance.USER, visibility=Visibility.PRIVATE, owner_profile=self.other, created_by=self.other)
        other_version = PresentationTemplateVersion.objects.create(template=private, version_number=1, status=VersionStatus.PUBLISHED, manifest=ESSENTIAL_MANIFEST, created_by=self.other)
        with self.assertRaises(PermissionDenied):
            upgrade_presentation(actor=self.owner, presentation=binding, template_version=other_version)
        binding.refresh_from_db()
        self.assertEqual(binding.template_version_id, old_id)
        upgrade_presentation(actor=self.owner, presentation=binding, template_version=self.templates["formal"])
        binding.refresh_from_db()
        self.assertEqual(binding.template_version_id, self.templates["formal"].pk)

    def test_forged_external_hero_url_is_not_accepted_as_editorial_asset(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("presentations:studio", kwargs={"activity_id": self.activity.pk}), {"purpose": PresentationPurpose.PUBLIC_PAGE, "template": "makolo-essential", "theme": "makolo-violet", "hero_image": "https://tracker.example/pixel.png", "action": "save"})
        self.assertEqual(response.status_code, 302)
        binding = ActivityPresentation.objects.get(activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        self.assertNotIn("hero_image", binding.editorial_data)

    def test_renderer_is_vertical_agnostic_for_event_transport_and_generic_activity(self):
        generic = create_activity(space=self.space, created_by=self.owner, title="Generic Activity")
        event_activity = create_activity(space=self.space, created_by=self.owner, title="Event Activity")
        Event.objects.create(activity=event_activity)
        transport_activity = create_activity(space=self.space, created_by=self.owner, title="Transport Activity")
        route = TransportRoute.objects.create(space=self.space, code="M3", name="Route M3")
        TransportService.objects.create(activity=transport_activity, route=route)
        for activity in (generic, event_activity, transport_activity):
            context = build_activity_context(activity=activity)
            html = render_presentation(manifest=ESSENTIAL_MANIFEST, theme_tokens=self.themes["makolo-violet"].tokens, context=context)
            self.assertIn(activity.title, html)
