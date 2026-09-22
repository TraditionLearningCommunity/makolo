from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import Access, AccessCredential, AccessStatus
from accounts.models import User, UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_group_role
from groups.models import Group
from groups.services import add_member, create_group
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from personal_assets.services import (
    archive_personal_asset,
    create_personal_asset,
    create_personal_asset_version,
)
from topics.models import ProfileInterest, Topic
from trust.credential_models import Credential, CredentialType
from trust.models import Proof, ProofStatus, ProofType


PASSWORD = "Makolo!2026-Z8-SecondaryA7"


class Z8SecondarySurfacesAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="z8-owner@makolo.test",
            username="z8-owner",
            password=PASSWORD,
            first_name="Amina",
            last_name="Z8",
        )
        UserProfile.objects.create(
            user=self.user,
            city="Lubumbashi",
            country="CD",
            public_profile=True,
        )
        self.other = User.objects.create_user(
            email="z8-other@makolo.test",
            username="z8-other",
            password=PASSWORD,
        )
        UserProfile.objects.create(user=self.other, public_profile=True)
        self.activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Activity Z8",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.client.force_authenticate(self.user)

    def _asset_with_versions(self, *, controller=None, title="CV Z8"):
        controller = controller or self.user
        asset = create_personal_asset(
            controller=controller,
            subject_profile=controller,
            title=title,
        )
        v1 = create_personal_asset_version(
            actor=controller,
            asset=asset,
            uploaded_file=SimpleUploadedFile(
                "cv-v1.pdf",
                b"%PDF-1.4 z8-v1",
                content_type="application/pdf",
            ),
            issued_at=date(2026, 1, 1),
            expires_at=date(2027, 1, 1),
        )
        v2 = create_personal_asset_version(
            actor=controller,
            asset=asset,
            uploaded_file=SimpleUploadedFile(
                "cv-v2.pdf",
                b"%PDF-1.4 z8-v2",
                content_type="application/pdf",
            ),
            issued_at=date(2026, 6, 1),
            expires_at=date(2027, 6, 1),
        )
        return asset, v1, v2

    def test_passport_keeps_declared_proof_credential_and_public_privacy_distinct(self):
        public_topic = Topic.objects.create(code="z8-public", label="Public Z8")
        private_topic = Topic.objects.create(code="z8-private", label="Privé Z8")
        ProfileInterest.objects.create(
            profile=self.user,
            topic=public_topic,
            is_public=True,
        )
        ProfileInterest.objects.create(
            profile=self.user,
            topic=private_topic,
            is_public=False,
        )
        proof = Proof.objects.create(
            subject_profile=self.user,
            journey=self.journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
            is_public=True,
            issued_by=self.user,
        )
        credential = Credential.objects.create(
            subject_profile=self.user,
            issuer_profile=self.user,
            issued_by=self.user,
            activity=self.activity,
            journey=self.journey,
            credential_type=CredentialType.ATTESTATION,
            title="Attestation Z8",
        )
        access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            journey=self.journey,
            issued_by=self.user,
            status=AccessStatus.VALID,
        )
        access_credential = AccessCredential.objects.create(access=access)

        complete = self.client.get("/api/v1/me/passport/")
        public = self.client.get("/api/v1/me/passport/?variant=public")

        self.assertEqual(complete.status_code, 200)
        self.assertEqual(public.status_code, 200)
        complete_data = complete.json()["data"]
        public_data = public.json()["data"]

        self.assertEqual(
            complete_data["established"]["proofs"][0]["kind"],
            "proof",
        )
        self.assertEqual(
            complete_data["established"]["proofs"][0]["id"],
            str(proof.pk),
        )
        self.assertEqual(
            complete_data["issued"]["credentials"][0]["kind"],
            "credential",
        )
        self.assertEqual(
            complete_data["issued"]["credentials"][0]["id"],
            str(credential.pk),
        )
        self.assertNotEqual(str(proof.pk), str(credential.pk))
        self.assertIn(
            "Privé Z8",
            [
                row["topic"]["label"]
                for row in complete_data["declared"]["interests"]
            ],
        )
        self.assertNotIn(
            "Privé Z8",
            [
                row["topic"]["label"]
                for row in public_data["declared"]["interests"]
            ],
        )
        serialized = str(complete.json())
        self.assertNotIn(str(access_credential.pk), serialized)
        self.assertNotIn(str(access_credential.public_id), serialized)
        self.assertNotIn(self.user.email, serialized)
        self.assertEqual(
            complete_data["projection"]["visibility"],
            "subject_private",
        )

    def test_passport_custom_revalidates_selection_and_cannot_switch_subject(self):
        other_activity = Activity.objects.create(
            owner_profile=self.other,
            created_by=self.other,
            title="Activity privée autre Z8",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        denied = self.client.get(
            f"/api/v1/me/passport/?variant=custom&activity={other_activity.pk}"
        )
        override = self.client.get(
            f"/api/v1/me/passport/?profile_id={self.other.pk}"
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(override.status_code, 400)

    def test_resources_are_owner_scoped_searchable_paged_and_storage_safe(self):
        asset, _, current = self._asset_with_versions(title="Curriculum Vitae Z8")
        other_asset, _, other_current = self._asset_with_versions(
            controller=self.other,
            title="Secret autre Z8",
        )

        response = self.client.get("/api/v1/me/resources/?q=Curriculum&limit=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        documents = data["documents"]
        self.assertEqual(documents["page"]["count"], 1)
        self.assertEqual(documents["items"][0]["id"], str(asset.pk))
        self.assertEqual(
            documents["items"][0]["current_version"]["version"],
            current.version,
        )
        self.assertIn("view_detail", documents["items"][0]["capabilities"])
        self.assertIn("download", documents["items"][0]["capabilities"])
        self.assertIn("reuse_in_journey", documents["items"][0]["capabilities"])

        serialized = str(response.json())
        self.assertNotIn(str(other_asset.pk), serialized)
        self.assertNotIn(str(other_current.pk), serialized)
        self.assertNotIn("Secret autre Z8", serialized)
        self.assertNotIn("content_hash", serialized)
        self.assertNotIn("personal_assets/", serialized)
        self.assertNotIn("file", documents["items"][0])
        self.assertFalse(
            data["invariants"]["personal_asset_satisfies_requirement_by_presence"]
        )

    def test_resource_detail_versions_download_and_idor(self):
        asset, old, current = self._asset_with_versions()
        other_asset, _, other_current = self._asset_with_versions(
            controller=self.other,
            title="Autre ressource Z8",
        )

        response = self.client.get(f"/api/v1/me/resources/{asset.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["current_version"]["id"], str(current.pk))
        self.assertTrue(data["current_version"]["current"])
        self.assertEqual(data["versions"]["page"]["count"], 2)
        self.assertEqual(
            {row["id"] for row in data["versions"]["items"]},
            {str(old.pk), str(current.pk)},
        )
        self.assertEqual(
            data["requirement"]["satisfied_by_presence"],
            False,
        )
        serialized = str(response.json())
        self.assertNotIn("content_hash", serialized)
        self.assertNotIn("personal_assets/", serialized)

        download = self.client.get(
            f"/api/v1/me/resources/versions/{current.pk}/download/"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Cache-Control"], "private, no-store")

        self.assertEqual(
            self.client.get(f"/api/v1/me/resources/{other_asset.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/me/resources/versions/{other_current.pk}/download/"
            ).status_code,
            404,
        )

    def test_archived_resource_remains_inspectable_but_not_downloadable(self):
        asset, _, current = self._asset_with_versions(title="Archive Z8")
        archive_personal_asset(actor=self.user, asset=asset)

        collection = self.client.get("/api/v1/me/resources/")
        self.assertNotIn(
            str(asset.pk),
            [row["id"] for row in collection.json()["data"]["documents"]["items"]],
        )
        detail = self.client.get(f"/api/v1/me/resources/{asset.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["status"], "archived")
        self.assertNotIn("download", detail.json()["data"]["capabilities"])
        self.assertEqual(
            self.client.get(
                f"/api/v1/me/resources/versions/{current.pk}/download/"
            ).status_code,
            404,
        )

    def test_reuse_creates_journey_artifact_without_satisfying_requirement(self):
        _, _, current = self._asset_with_versions(title="CV à réutiliser Z8")

        response = self.client.post(
            f"/api/v1/me/resources/versions/{current.pk}/reuse/",
            {"journey_id": str(self.journey.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["source"]["id"], str(current.pk))
        self.assertEqual(data["result"]["kind"], "journey_artifact")
        self.assertFalse(data["requirement"]["satisfied"])

    def test_group_membership_is_relationship_not_authority(self):
        group = create_group(actor=self.other, name="Groupe membre Z8")
        add_member(actor=self.other, group=group, profile=self.user)

        response = self.client.get(
            f"/api/v1/me/collectives/groups/{group.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["relationship"]["membership"]["active"])
        self.assertFalse(data["relationship"]["authority"]["authorized"])
        self.assertEqual(data["relationship"]["responsibility"], None)
        self.assertIn("view", data["capabilities"])
        self.assertIn("leave", data["capabilities"])
        for capability in (
            "edit",
            "manage_members",
            "invite",
            "manage_ownership",
        ):
            self.assertNotIn(capability, data["capabilities"])

    def test_group_real_mandate_drives_capabilities_and_is_scope_bound(self):
        group = create_group(actor=self.other, name="Groupe autorisé Z8")
        other_group = create_group(actor=self.other, name="Autre groupe Z8")
        grant_group_role(
            profile=self.user,
            group=group,
            role=SystemRoleCode.GROUP_ADMIN,
            granted_by=self.other,
        )

        response = self.client.get(
            f"/api/v1/me/collectives/groups/{group.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["relationship"]["authority"]["authorized"])
        self.assertTrue(data["relationship"]["authority"]["management_authorized"])
        self.assertIn("edit", data["capabilities"])
        self.assertIn("manage_members", data["capabilities"])
        self.assertFalse(
            can(self.user, PermissionCode.GROUP_MANAGE, group=other_group)
        )

    def test_group_outsider_is_404_and_space_group_membership_grants_no_space_authority(self):
        outsider_group = create_group(actor=self.other, name="Groupe privé Z8")
        self.assertEqual(
            self.client.get(
                f"/api/v1/me/collectives/groups/{outsider_group.pk}/"
            ).status_code,
            404,
        )

        space = Organization.objects.create(
            name="Espace Z8",
            created_by=self.other,
        )
        group = Group.objects.create(
            name="Groupe Espace Z8",
            space=space,
            created_by=self.other,
        )
        # Give the owner actor just enough canonical authority to add a member.
        from authorization.services import grant_space_role

        grant_space_role(
            profile=self.other,
            space=space,
            role=SystemRoleCode.SPACE_OWNER,
            source="z8-test",
        )
        add_member(actor=self.other, group=group, profile=self.user)

        response = self.client.get(
            f"/api/v1/me/collectives/groups/{group.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.json()["data"]["relationship"]["authority"]["management_authorized"]
        )
        self.assertFalse(
            can(self.user, PermissionCode.SPACE_GROUPS_MANAGE, space)
        )

    def test_moi_previews_link_to_z8_depths(self):
        asset, _, _ = self._asset_with_versions(title="Lien Z8")
        group = create_group(actor=self.other, name="Groupe lien Z8")
        add_member(actor=self.other, group=group, profile=self.user)

        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        resource = next(
            row
            for row in data["resources"]["documents"]["items"]
            if row["id"] == str(asset.pk)
        )
        collective = next(
            row
            for row in data["collectives"]["groups"]["items"]
            if row["id"] == str(group.pk)
        )
        self.assertEqual(
            resource["links"]["detail"],
            f"/api/v1/me/resources/{asset.pk}/",
        )
        self.assertEqual(
            collective["links"]["detail"],
            f"/api/v1/me/collectives/groups/{group.pk}/",
        )
