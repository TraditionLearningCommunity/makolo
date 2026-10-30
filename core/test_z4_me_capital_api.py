from django.test import TestCase
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from activities.models import Activity, ActivityStatus
from discovery.models import ActivityBookmark
from groups.models import Group
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from partners.models import Partner, PartnerStatus
from personal_assets.models import PersonalAsset
from topics.models import OpenToKind, ProfileInterest, ProfileOpenTo, Topic


PASSWORD = "Makolo!2026-Z4-CapitalA7"


class PersonalMeCapitalAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="z4-capital@makolo.test",
            username="z4-capital",
            password=PASSWORD,
            first_name="Amina",
            last_name="Capital",
        )
        UserProfile.objects.create(user=self.user, city="Lubumbashi", country="CD")
        self.other = User.objects.create_user(
            email="z4-capital-other@makolo.test",
            username="z4-capital-other",
            password=PASSWORD,
        )
        UserProfile.objects.create(user=self.other)
        self.client.force_authenticate(self.user)

    def test_considerations_keep_explicit_concepts_separate(self):
        topic = Topic.objects.create(code="z4-technology", label="Technologie")
        interest = ProfileInterest.objects.create(
            profile=self.user,
            topic=topic,
            is_public=False,
        )
        open_to = ProfileOpenTo.objects.create(
            profile=self.user,
            kind=OpenToKind.MENTOR,
            topic=topic,
            is_active=True,
            is_public=False,
            is_searchable=False,
        )
        activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Atelier Z4",
            status=ActivityStatus.PUBLISHED,
        )
        bookmark = ActivityBookmark.objects.create(user=self.user, activity=activity)

        response = self.client.get("/api/v1/me/considerations/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["projection"], "personal.me.considerations")
        data = payload["data"]
        self.assertEqual(data["interests"]["items"][0]["id"], str(interest.pk))
        self.assertEqual(data["interests"]["items"][0]["topic"]["label"], "Technologie")
        self.assertFalse(data["interests"]["items"][0]["public"])
        self.assertEqual(data["open_to"]["items"][0]["id"], str(open_to.pk))
        self.assertEqual(data["open_to"]["items"][0]["kind"], OpenToKind.MENTOR)
        self.assertFalse(data["open_to"]["items"][0]["searchable"])
        self.assertEqual(data["bookmarks"]["items"][0]["id"], str(bookmark.pk))
        self.assertEqual(data["bookmarks"]["items"][0]["activity"]["id"], str(activity.pk))
        self.assertEqual(data["watches"]["items"], [])
        self.assertNotIn("criteria", str(data["watches"]))

    def test_bookmarked_media_reuses_published_recognition_only(self):
        from activities.models import ActivityVisibility

        activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Formation reconnue",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        ActivityBookmark.objects.create(user=self.user, activity=activity)
        media = SimpleNamespace(
            use_id="ea1a8fe1-3549-4ad1-86a2-bad932f2a235",
            mime_type="image/jpeg",
            alt_text="Salle de formation",
        )
        with patch(
            "presentations.media_selectors.public_presentation_media_for_activities",
            return_value={str(activity.pk): [media]},
        ):
            response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        row = response.json()["data"]["considerations"]["bookmarks"]["items"][0]
        binding = row["media_bindings"][0]
        self.assertEqual(binding["purpose"], "RECOGNIZE")
        self.assertEqual(binding["target"], {"kind": "activity", "id": str(activity.pk)})
        self.assertEqual(binding["resource"]["mime_type"], "image/jpeg")
        self.assertEqual(binding["resource"]["alt_text"], "Salle de formation")
        self.assertIn("/media/uses/", binding["resource"]["url"])
        self.assertNotIn("file_path", str(binding))

    def test_saved_media_is_also_available_on_bounded_continuation(self):
        from activities.models import ActivityVisibility

        activities = []
        for index in range(7):
            activity = Activity.objects.create(
                owner_profile=self.user,
                created_by=self.user,
                title=f"Possibilité {index}",
                status=ActivityStatus.PUBLISHED,
                visibility=ActivityVisibility.PUBLIC,
            )
            ActivityBookmark.objects.create(user=self.user, activity=activity)
            activities.append(activity)
        oldest = activities[0]
        media = SimpleNamespace(
            use_id="ea1a8fe1-3549-4ad1-86a2-bad932f2a235",
            mime_type="image/png",
            alt_text="Lieu de la possibilité",
        )
        with patch(
            "presentations.media_selectors.public_presentation_media_for_activities",
            return_value={str(oldest.pk): [media]},
        ):
            root = self.client.get("/api/v1/me/")
            page = self.client.get(
                "/api/v1/me/preview/considerations/",
                {"family": "bookmarks", "offset": 6, "limit": 24},
            )
        self.assertEqual(root.status_code, 200)
        self.assertEqual(page.status_code, 200)
        initial = root.json()["data"]["considerations"]["bookmarks"]
        self.assertEqual(initial["next_offset"], 6)
        self.assertTrue(initial["has_more"])
        continued = page.json()["data"]["collection"]
        self.assertEqual(len(continued["items"]), 1)
        self.assertFalse(continued["has_more"])
        row = continued["items"][0]
        self.assertEqual(row["activity"]["id"], str(oldest.pk))
        self.assertEqual(row["media_bindings"][0]["purpose"], "RECOGNIZE")

    def test_private_bookmark_does_not_reveal_media(self):
        from activities.models import ActivityVisibility

        activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Contenu privé",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ActivityBookmark.objects.create(user=self.user, activity=activity)
        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        row = response.json()["data"]["considerations"]["bookmarks"]["items"][0]
        self.assertEqual(row["activity"]["title"], "Contenu privé")
        self.assertNotIn("media_bindings", row)

    def test_team_membership_is_not_projected_as_authority(self):
        organization = Organization.objects.create(
            name="Collectif Z4",
            created_by=self.other,
        )
        team = Team.objects.create(
            organization=organization,
            name="Équipe Z4",
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.user,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=self.other,
        )
        group = Group.objects.create(
            name="Groupe personnel Z4",
            owner_profile=self.user,
            created_by=self.user,
        )

        response = self.client.get("/api/v1/me/collectives/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["authorized_spaces"]["items"], [])
        self.assertEqual(data["teams"]["count"], 1)
        team_item = data["teams"]["items"][0]
        self.assertEqual(team_item["id"], str(team.pk))
        self.assertEqual(team_item["relationship"], "membership")
        self.assertNotIn("can_act", team_item)
        self.assertNotIn("permissions", team_item)
        self.assertNotIn("mandates", team_item)
        self.assertEqual(data["groups"]["items"][0]["id"], str(group.pk))

    def test_resources_expose_metadata_without_private_file_contract(self):
        asset = PersonalAsset.objects.create(
            controller=self.user,
            subject_profile=self.user,
            title="Passeport personnel",
        )
        PersonalAsset.objects.create(
            controller=self.other,
            subject_profile=self.other,
            title="Document secret tiers",
        )

        response = self.client.get("/api/v1/me/resources/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["documents"]["count"], 1)
        item = data["documents"]["items"][0]
        self.assertEqual(item["id"], str(asset.pk))
        self.assertEqual(item["title"], "Passeport personnel")
        self.assertIsNone(item["latest_version"])
        serialized = str(response.json())
        self.assertNotIn("Document secret tiers", serialized)
        self.assertNotIn("file", item)
        self.assertNotIn("content_hash", item)
        self.assertNotIn("download", item)
        self.assertEqual(data["proofs"]["items"], [])
        self.assertEqual(data["credentials"]["items"], [])

    def test_passport_reuses_canonical_projection_and_respects_variant_privacy(self):
        topic = Topic.objects.create(code="z4-private-topic", label="Sujet privé")
        ProfileInterest.objects.create(
            profile=self.user,
            topic=topic,
            is_public=False,
        )

        complete = self.client.get("/api/v1/me/passport/")
        public = self.client.get("/api/v1/me/passport/?variant=public")

        self.assertEqual(complete.status_code, 200)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(
            complete.json()["meta"]["projection"],
            "personal.me.passport",
        )
        self.assertEqual(complete.json()["data"]["variant"], "complete")
        self.assertIn("private_details", complete.json()["data"])
        self.assertEqual(
            complete.json()["data"]["private_details"]["username"],
            self.user.username,
        )
        self.assertEqual(
            complete.json()["data"]["declared"]["interests"][0]["topic"]["label"],
            "Sujet privé",
        )
        self.assertEqual(public.json()["data"]["variant"], "public")
        self.assertNotIn("private_details", public.json()["data"])
        self.assertEqual(public.json()["data"]["declared"]["interests"], [])
        for variant in ("thematic", "custom"):
            response = self.client.get(f"/api/v1/me/passport/?variant={variant}")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("private_details", response.json()["data"])

    def test_personalized_passport_api_requires_explicit_disclosure_selection(self):
        self.user.bio = "Description privée pour mon Passeport"
        self.user.metadata = {"avatar_url": "/media/private-personal-avatar.jpg"}
        self.user.save(update_fields=["bio", "metadata", "updated_at"])

        identity_only = self.client.get("/api/v1/me/passport/?variant=custom")
        self.assertEqual(identity_only.status_code, 200)
        empty = identity_only.json()["data"]
        self.assertEqual(empty["identity"]["avatar_url"], "")
        self.assertEqual(empty["identity"]["bio"], "")
        self.assertEqual(empty["activities"], [])
        self.assertNotIn("private_details", empty)

        deliberate = self.client.get(
            "/api/v1/me/passport/?variant=custom&include=bio&include=avatar",
        )
        self.assertEqual(deliberate.status_code, 200)
        selected = deliberate.json()["data"]
        self.assertEqual(
            selected["identity"]["bio"], "Description privée pour mon Passeport",
        )
        self.assertEqual(
            selected["identity"]["avatar_url"], "/media/private-personal-avatar.jpg",
        )
        self.assertNotIn("private_details", selected)

    def test_passport_collective_context_is_owner_only_and_not_authority(self):
        organization = Organization.objects.create(
            name="Collectif CV Z4", created_by=self.other,
        )
        team = Team.objects.create(
            organization=organization, name="Équipe CV Z4", is_active=True,
        )
        TeamMembership.objects.create(
            team=team, user=self.user, status=TeamMembershipStatus.ACTIVE,
        )

        complete = self.client.get("/api/v1/me/passport/")
        self.assertEqual(complete.status_code, 200)
        data = complete.json()["data"]
        self.assertEqual(
            data["collectives"]["team_affiliations"],
            [{"team": "Équipe CV Z4", "space": "Collectif CV Z4"}],
        )
        self.assertEqual(data["collectives"]["active_space_mandates"], [])

        for variant in ("public", "thematic", "custom"):
            response = self.client.get(f"/api/v1/me/passport/?variant={variant}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["data"]["collectives"]["team_affiliations"], [],
            )
            self.assertEqual(
                response.json()["data"]["collectives"]["active_space_mandates"], [],
            )

    def test_dated_history_api_never_reads_another_profiles_snapshots(self):
        from sharing.passport import build_profile_passport
        from sharing.passport_documents import issue_passport_snapshot

        mine = issue_passport_snapshot(build_profile_passport(self.user, variant="complete"))
        another = issue_passport_snapshot(build_profile_passport(self.other, variant="complete"))
        listing = self.client.get("/api/v1/me/passport/history/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["data"]["count"], 1)
        self.assertEqual(listing.json()["data"]["items"][0]["id"], str(mine.pk))
        self.assertEqual(listing["Cache-Control"], "private, no-store")
        one = self.client.get(f"/api/v1/me/passport/history/{mine.pk}/")
        self.assertEqual(one.status_code, 200)
        self.assertEqual(one.json()["data"]["document_id"], mine.document_id)
        denied = self.client.get(f"/api/v1/me/passport/history/{another.pk}/")
        self.assertEqual(denied.status_code, 404)

    def test_passport_pdf_is_authenticated_and_issues_verifiable_snapshot(self):
        from sharing.models import PassportSnapshot

        topic = Topic.objects.create(code="z4-pdf", label="Culture")
        ProfileInterest.objects.create(profile=self.user, topic=topic, is_public=True)
        response = self.client.get("/api/v1/me/passport/pdf/?variant=complete")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        snapshot = PassportSnapshot.objects.get(profile=self.user)
        self.assertEqual(snapshot.variant, "complete")
        self.assertIn("Culture", str(snapshot.payload["interests"]))

        self.client.force_authenticate(user=None)
        anonymous = self.client.get("/api/v1/me/passport/pdf/")
        self.assertIn(anonymous.status_code, (401, 403))
        self.assertEqual(PassportSnapshot.objects.count(), 1)

    def test_passport_pdf_rejects_invalid_custom_selection(self):
        topic = Topic.objects.create(code="z4-pdf-private", label="Sujet")
        ProfileInterest.objects.create(profile=self.user, topic=topic)
        response = self.client.get(
            "/api/v1/me/passport/pdf/?variant=custom&activity="
            "00000000-0000-0000-0000-000000000001&include=interests"
        )
        self.assertEqual(response.status_code, 403)

    def test_partner_projection_is_personal_and_minimally_disclosed(self):
        organization = Organization.objects.create(
            name="Espace partenaire Z4",
            created_by=self.other,
        )
        mine = Partner.objects.create(
            organization=organization,
            user=self.user,
            kind="ambassador",
            status=PartnerStatus.ACTIVE,
            name="Amina Ambassadrice",
            email=self.user.email,
            phone="+243999111222",
        )
        Partner.objects.create(
            organization=organization,
            user=self.other,
            kind="ambassador",
            status=PartnerStatus.ACTIVE,
            name="Partenaire tiers",
            email=self.other.email,
        )

        response = self.client.get("/api/v1/me/partners/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["relationships"]["count"], 1)
        item = data["relationships"]["items"][0]
        self.assertEqual(item["id"], str(mine.pk))
        self.assertEqual(item["space"]["name"], "Espace partenaire Z4")
        self.assertNotIn("email", item)
        self.assertNotIn("phone", item)
        serialized = str(response.json())
        self.assertNotIn(self.user.email, serialized)
        self.assertNotIn(self.other.email, serialized)
        self.assertNotIn("Partenaire tiers", serialized)

    def test_root_me_composes_bounded_human_territories(self):
        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("identity", data)
        self.assertIn("passport", data)
        self.assertIn("considerations", data)
        self.assertIn("collectives", data)
        self.assertIn("resources", data)
        self.assertIn("support", data)
        self.assertLessEqual(len(data["considerations"]["interests"]["items"]), 6)
        self.assertLessEqual(len(data["collectives"]["groups"]["items"]), 6)
        self.assertLessEqual(len(data["resources"]["documents"]["items"]), 6)

    def test_root_me_marks_a_bounded_section_partial(self):
        for index in range(7):
            PersonalAsset.objects.create(
                controller=self.user,
                subject_profile=self.user,
                title=f"Document {index}",
            )

        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["sections"]["resources"], {"state": "partial"})
        self.assertTrue(data["resources"]["documents"]["has_more"])

    def test_all_personal_depths_require_auth_and_reject_profile_override(self):
        paths = (
            "/api/v1/me/considerations/",
            "/api/v1/me/collectives/",
            "/api/v1/me/passport/",
            "/api/v1/me/resources/",
            "/api/v1/me/partners/",
        )
        other_client = APIClient()
        for path in paths:
            with self.subTest(path=path):
                unauthenticated = other_client.get(path)
                self.assertEqual(unauthenticated.status_code, 401)
                overridden = self.client.get(f"{path}?profile_id={self.other.pk}")
                self.assertEqual(overridden.status_code, 400)
                self.assertEqual(
                    overridden.json()["error"]["code"],
                    "validation_error",
                )
