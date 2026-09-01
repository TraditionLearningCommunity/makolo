from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from access.models import AccessStatus
from access.services import issue_access
from activities.services import create_activity, create_occurrence

from .contexts import build_access_context, build_activity_context
from .enums import PresentationPurpose, Provenance, VersionStatus, Visibility
from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from .manifests.validation import validate_manifest
from .models import PresentationTemplate, PresentationTemplateVersion
from .rendering import render_presentation
from .resolver import resolve_presentation
from .themes import validate_theme_tokens

User = get_user_model()


class PresentationFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mps-owner", email="mps@example.test", password="StrongPass2026!")
        self.activity = create_activity(owner_profile=self.user, created_by=self.user, title="Forum Makolo")
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=3),
            timezone="Africa/Lubumbashi",
        )

    def test_makolo_template_ownership_is_explicit(self):
        template = PresentationTemplate(slug="essential", name="Essential", provenance=Provenance.MAKOLO, visibility=Visibility.PUBLIC, created_by=self.user)
        template.save()
        self.assertIsNone(template.owner_profile_id)
        self.assertIsNone(template.owner_space_id)

    def test_published_template_version_is_immutable(self):
        template = PresentationTemplate.objects.create(slug="essential", name="Essential", provenance=Provenance.MAKOLO, visibility=Visibility.PUBLIC, created_by=self.user)
        version = PresentationTemplateVersion.objects.create(template=template, version_number=1, status=VersionStatus.PUBLISHED, schema_version=1, manifest=ESSENTIAL_MANIFEST, created_by=self.user)
        version.manifest = {**ESSENTIAL_MANIFEST, "surfaces": ["web"]}
        with self.assertRaises(ValidationError):
            version.save()

    def test_theme_rejects_unknown_token(self):
        with self.assertRaises(ValidationError):
            validate_theme_tokens({"tracking_pixel": "x"})

    def test_manifest_rejects_unknown_component_and_sensitive_binding(self):
        broken = {"schema_version": 1, "purposes": ["invitation"], "surfaces": ["web"], "layout": {"component": "Unknown", "props": {}}}
        with self.assertRaises(ValidationError):
            validate_manifest(broken)
        sensitive = {"schema_version": 1, "purposes": ["invitation"], "surfaces": ["web"], "layout": {"component": "Text", "props": {"value": {"binding": "activity.owner.user.password"}}}}
        with self.assertRaises(ValidationError):
            validate_manifest(sensitive)

    def test_manifest_rejects_dangerous_url_and_depth(self):
        dangerous = {"schema_version": 1, "purposes": ["invitation"], "surfaces": ["web"], "layout": {"component": "Image", "props": {"src": "javascript:alert(1)", "alt": "x"}}}
        with self.assertRaises(ValidationError):
            validate_manifest(dangerous)
        node = {"component": "Stack", "props": {}, "children": []}
        root = node
        for _ in range(13):
            child = {"component": "Stack", "props": {}, "children": []}
            node["children"] = [child]
            node = child
        deep = {"schema_version": 1, "purposes": ["invitation"], "surfaces": ["web"], "layout": root}
        with self.assertRaises(ValidationError):
            validate_manifest(deep)

    def test_xss_editorial_is_escaped(self):
        context = build_activity_context(activity=self.activity, occurrence=self.occurrence, editorial={"intro": "<img src=x onerror=alert(1)>"})
        html = render_presentation(manifest=ESSENTIAL_MANIFEST, theme_tokens=ESSENTIAL_THEME, context=context)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img", html)

    def test_resolver_falls_back_without_backfill(self):
        resolved = resolve_presentation(activity=self.activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        self.assertIsNone(resolved.binding)
        self.assertEqual(resolved.fallback_reason, "makolo-essential")

    def test_access_qr_is_visual_only_and_raw_credential_not_in_html(self):
        access = issue_access(beneficiary=self.user, activity=self.activity, occurrence=self.occurrence, issued_by=self.user, status=AccessStatus.VALID)
        credential = access.credentials.first()
        from access.services import render_access_credential
        raw = render_access_credential(credential)
        context = build_access_context(access=access, credential=credential)
        html = render_presentation(manifest=ESSENTIAL_MANIFEST, theme_tokens=ESSENTIAL_THEME, context=context)
        self.assertIn("data:image/png;base64,", html)
        self.assertNotIn(raw, html)
        self.assertNotIn(str(credential.public_id), html)

    def test_occurrence_context_rejects_cross_activity(self):
        other = create_activity(owner_profile=self.user, created_by=self.user, title="Autre")
        with self.assertRaises(ValueError):
            build_activity_context(activity=other, occurrence=self.occurrence)
