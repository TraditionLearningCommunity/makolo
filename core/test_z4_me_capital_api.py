from django.test import TestCase

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
        self.assertEqual(
            complete.json()["data"]["declared"]["interests"][0]["topic"]["label"],
            "Sujet privé",
        )
        self.assertEqual(public.json()["data"]["variant"], "public")
        self.assertEqual(public.json()["data"]["declared"]["interests"], [])

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
