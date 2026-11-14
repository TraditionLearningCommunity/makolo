"""Targeted contract coverage for Space Resources composed in Nous."""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization
from personal_assets.models import PersonalAsset
from presentations.asset_models import PresentationAsset
from presentations.enums import Provenance, VersionStatus, Visibility
from presentations.essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from presentations.models import (
    PresentationTemplate,
    PresentationTemplateVersion,
    PresentationTheme,
    PresentationThemeVersion,
)
from sharing.models import PassportSnapshot, PublicSubjectKind
from space_assets.models import SpaceDocument
from trust.credential_models import Credential, CredentialType


class SpaceUsResourcesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="us-res-owner", password="x")
        self.other_owner = User.objects.create_user(
            username="us-res-other-owner", password="x"
        )
        self.member = User.objects.create_user(username="us-res-member", password="x")
        self.outsider = User.objects.create_user(
            username="us-res-outsider", password="x"
        )
        self.space = Organization.objects.create(
            name="Ressources Space", slug="ressources-space", created_by=self.owner,
        )
        self.other_space = Organization.objects.create(
            name="Autre Space", slug="autre-ressources", created_by=self.outsider,
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        grant_space_role(
            profile=self.other_owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.url = (
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/resources/"
        )

    def _snapshot(self, space, *, variant="complete"):
        return PassportSnapshot.objects.create(
            subject_kind=PublicSubjectKind.SPACE,
            space=space,
            public_identifier=space.slug,
            variant=variant,
            payload={},
            payload_hash="0" * 64,
        )

    def _template(self, space):
        template = PresentationTemplate.objects.create(
            slug="collectif",
            name="Modèle institutionnel",
            provenance=Provenance.SPACE,
            visibility=Visibility.SPACE,
            owner_space=space,
            created_by=self.owner,
        )
        return PresentationTemplateVersion.objects.create(
            template=template,
            version_number=1,
            status=VersionStatus.PUBLISHED,
            schema_version=1,
            manifest=ESSENTIAL_MANIFEST,
            created_by=self.owner,
        )

    def _theme(self, space):
        theme = PresentationTheme.objects.create(
            slug="identite",
            name="Thème institutionnel",
            provenance=Provenance.SPACE,
            visibility=Visibility.SPACE,
            owner_space=space,
            created_by=self.owner,
        )
        return PresentationThemeVersion.objects.create(
            theme=theme,
            version_number=1,
            status=VersionStatus.PUBLISHED,
            schema_version=1,
            tokens=ESSENTIAL_THEME,
            created_by=self.owner,
        )
    def _asset(self, space):
        return PresentationAsset.objects.create(
            provenance=Provenance.SPACE,
            owner_space=space,
            uploaded_by=self.owner,
            mime_type="image/png",
            size=4,
            checksum="a" * 64,
        )

    def _credential(self, space):
        activity = Activity.objects.create(
            title="Activité certifiante",
            slug="activite-certifiante",
            created_by=self.owner,
            space=space,
        )
        return Credential.objects.create(
            subject_profile=self.member,
            issuer_space=space,
            issued_by=self.owner,
            activity=activity,
            credential_type=CredentialType.ATTESTATION,
            title="Attestation institutionnelle",
        )


    def test_n1_and_n2_compose_only_genuine_space_owners(self):
        self._snapshot(self.space)
        self._template(self.space)
        self._theme(self.space)
        self._asset(self.space)
        self._credential(self.space)
        self._snapshot(self.other_space, variant="public")
        PersonalAsset.objects.create(
            controller=self.owner,
            subject_profile=self.owner,
            title="Document personnel secret",
        )
        self.client.force_authenticate(self.owner)
        root = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(root.status_code, 200, root.data)
        self.assertEqual(root.data["resources"]["visibility"], "visible")
        self.assertEqual(root.data["resources"]["count"], 4)
        self.assertEqual(
            root.data["handoffs"]["resources"],
            f"/space/{self.space.slug}/us/resources",
        )
        self.assertEqual(
            {row["owner"] for row in root.data["resources"]["items"]},
            {"presentations", "trust"},
        )
        self.assertNotIn("Document personnel secret", str(root.data))
        self.assertNotIn(self.other_space.slug, str(root.data))
        self.assertNotIn("payload", str(root.data["resources"]))

        docs = self.client.get(self.url)
        self.assertEqual(docs.status_code, 200, docs.data)
        self.assertEqual(docs["Cache-Control"], "private, no-store")
        self.assertEqual(docs.data["items"], [])
        self.assertEqual(docs.data["counts"], {
            "document": 0,
            "asset": 1,
            "template": 1,
            "theme": 1,
            "credential": 1,
            "received_title": 0,
        })
        self.assertEqual(
            self.client.get(self.url + "?kind=template").data["items"][0]["title"],
            "Modèle institutionnel",
        )
        self.assertEqual(
            self.client.get(self.url + "?kind=theme").data["items"][0]["title"],
            "Thème institutionnel",
        )
        self.assertEqual(
            self.client.get(self.url + "?kind=asset").data["items"][0]["owner"],
            "presentations",
        )
        self.assertEqual(
            self.client.get(self.url + "?kind=credential").data["items"][0]["title"],
            "Attestation institutionnelle",
        )
        self.assertNotIn("payload", str(docs.data))

    def test_received_titles_are_a_document_view_without_double_counting(self):
        SpaceDocument.objects.create(
            space=self.space,
            title="Attestation externe",
            kind="certificate",
            visibility="internal",
            created_by=self.owner,
        )
        self.client.force_authenticate(self.owner)

        received = self.client.get(self.url + "?kind=received_title")
        self.assertEqual(received.status_code, 200, received.data)
        self.assertEqual(received.data["count"], 1)
        self.assertEqual(received.data["items"][0]["title"], "Attestation externe")
        self.assertEqual(received.data["items"][0]["owner"], "space_assets")
        self.assertEqual(received.data["counts"]["document"], 1)
        self.assertEqual(received.data["counts"]["received_title"], 1)
        self.assertEqual(received.data["total_count"], 1)

    def test_foreign_member_and_viewer_without_authority_are_refused(self):
        self._snapshot(self.space)
        for viewer in (self.member, self.outsider):
            self.client.force_authenticate(viewer)
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertNotIn(
                "resources",
                self.client.get(
                    f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
                ).data.get("handoffs", {}),
            )

    def test_space_reader_without_management_and_activity_limited_are_restricted(self):
        self._snapshot(self.space)
        marketing = User.objects.create_user(
            username="us-res-marketing", password="x",
        )
        grant_space_role(
            profile=marketing, space=self.space,
            role=SystemRoleCode.MARKETING, granted_by=self.owner,
        )
        self.client.force_authenticate(marketing)
        root = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(root.status_code, 200, root.data)
        # A Space-view mandate may expose public-facing Presentation resources,
        # but never confidential documents, media or Trust-issued titles.
        self.assertEqual(root.data["resources"]["counts"]["document"], 0)
        self.assertEqual(root.data["resources"]["counts"]["asset"], 0)
        self.assertEqual(root.data["resources"]["counts"]["credential"], 0)
        self.assertEqual(root.data["resources"]["counts"]["received_title"], 0)
        self.assertEqual(
            self.client.get(self.url).status_code, 200,
        )
        self.assertEqual(self.client.get(self.url).data["items"], [])

        activity = Activity.objects.create(
            title="Activité locale", slug="us-res-local",
            created_by=self.owner, space=self.space,
        )
        scoped = User.objects.create_user(username="us-res-scoped", password="x")
        grant_activity_role(
            profile=scoped, activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER, granted_by=self.owner,
        )
        self.client.force_authenticate(scoped)
        root = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(root.status_code, 200, root.data)
        self.assertEqual(root.data["resources"]["visibility"], "restricted")
        self.assertNotIn("resources", root.data["handoffs"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_owner_revocation_invalidates_n2_and_preview(self):
        self._snapshot(self.space)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        revoke_mandate(mandate=self.owner_mandate, actor=self.other_owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_revoked_passports_and_unpublished_templates_are_not_presented(self):
        snapshot = self._snapshot(self.space)
        snapshot.revoked_at = timezone.now()
        snapshot.save(update_fields=["revoked_at"])
        template = PresentationTemplate.objects.create(
            slug="brouillon", name="Modèle brouillon",
            provenance=Provenance.SPACE, visibility=Visibility.SPACE,
            owner_space=self.space, created_by=self.owner,
        )
        PresentationTemplateVersion.objects.create(
            template=template, version_number=1,
            status=VersionStatus.DRAFT, manifest=ESSENTIAL_MANIFEST,
            created_by=self.owner,
        )
        self.client.force_authenticate(self.owner)
        root = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(root.data["resources"]["count"], 0)
        self.assertNotIn("Modèle brouillon", str(root.data))
        self.assertNotIn(str(snapshot.pk), str(root.data))

    def test_resource_listing_pages_and_validates_query(self):
        for _ in range(23):
            self._asset(self.space)
        self.client.force_authenticate(self.owner)
        first = self.client.get(self.url + "?kind=asset")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(len(first.data["items"]), 20)
        self.assertTrue(first.data["has_more"])
        self.assertEqual(first.data["next_offset"], 20)
        second = self.client.get(self.url + "?kind=asset&offset=20")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(len(second.data["items"]), 3)
        self.assertFalse(second.data["has_more"])
        self.assertEqual(len({
            row["id"] for row in first.data["items"] + second.data["items"]
        }), 23)
        for query in ("?kind=private", "?offset=-1", "?offset=oops"):
            self.assertEqual(self.client.get(self.url + query).status_code, 400)

    def test_owner_source_failure_is_local_to_resources(self):
        self.client.force_authenticate(self.owner)
        with patch(
            "organizations.api.space_us_projection."
            "build_space_us_resources_projection",
            side_effect=RuntimeError("owner unavailable"),
        ):
            root = self.client.get(
                f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
            )
        self.assertEqual(root.status_code, 200, root.data)
        self.assertEqual(root.data["identity"]["name"], self.space.name)
        self.assertEqual(root.data["resources"]["visibility"], "unavailable")
        self.assertNotIn("resources", root.data["handoffs"])

    def test_empty_institutional_library_is_not_unknown_or_personal(self):
        self.client.force_authenticate(self.owner)
        root = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(root.data["resources"]["visibility"], "visible")
        self.assertEqual(root.data["resources"]["count"], 0)
        self.assertEqual(root.data["resources"]["items"], [])
        empty = self.client.get(self.url)
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.data["items"], [])
        self.assertEqual(empty.data["total_count"], 0)

    def test_web_resource_depth_preserves_active_viewer_perspective(self):
        from urllib.parse import urlencode

        self.client.force_login(self.owner)
        role_key = f"mandate:{self.owner_mandate.pk}"
        url = reverse("organizations:space-us", kwargs={"slug": self.space.slug})
        url += "?" + urlencode({"responsibility": role_key})
        root = self.client.get(url)
        self.assertEqual(root.status_code, 200)
        handoff = root.context["us_owner_links"]["resources"]
        self.assertIn("detail=resources", handoff)
        self.assertIn(urlencode({"responsibility": role_key}), handoff)
        depth = self.client.get(handoff)
        self.assertEqual(depth.status_code, 200)
        self.assertEqual(
            depth.context["selected_responsibility"]["key"], role_key,
        )
        self.assertIn(
            urlencode({"responsibility": role_key}),
            depth.context["resources_back_url"],
        )
        self.assertIn(
            urlencode({"responsibility": role_key}),
            depth.context["resources_base_url"],
        )

    def test_web_n2_resource_categories_and_authority(self):
        self._snapshot(self.space)
        self._template(self.space)
        self.client.force_login(self.owner)
        url = reverse("organizations:space-us", kwargs={"slug": self.space.slug})
        n1 = self.client.get(url)
        self.assertContains(n1, "Nos ressources")
        self.assertContains(n1, "Consulter les ressources")
        n2 = self.client.get(url + "?detail=resources")
        self.assertEqual(n2.status_code, 200)
        self.assertEqual(n2["Cache-Control"], "private, no-store")
        self.assertContains(n2, "Médias de présentation")
        self.assertContains(n2, "Modèles de présentation")
        self.assertContains(n2, "Thèmes de présentation")
        self.assertContains(n2, "Titres émis")
        self.assertContains(n2, "Titres reçus")
        self.assertNotContains(n2, "Passeports émis")
        template_n2 = self.client.get(url + "?detail=resources&kind=template")
        self.assertContains(template_n2, "Modèle institutionnel")
        self.assertContains(template_n2, reverse(
            "presentations:space-library", kwargs={"slug": self.space.slug}
        ))
        for query in ("?detail=resources&kind=forged", "?detail=resources&offset=-3"):
            self.assertEqual(self.client.get(url + query).status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url + "?detail=resources").status_code, 404)
