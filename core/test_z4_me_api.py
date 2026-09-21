from django.test import TestCase

from rest_framework.test import APIClient

from accounts.models import User, UserProfile


PASSWORD = "Makolo!2026-Z4-StrongA7"


class PersonalMeAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="z4-owner@makolo.test",
            username="z4-owner",
            password=PASSWORD,
            first_name="Amina",
            last_name="Kabongo",
            phone="+243999000111",
            bio="Ingénieure et formatrice.",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            profession="Ingénieure",
            city="Lubumbashi",
            country="CD",
            address="Adresse privée non projetée",
            latitude=-11.66,
            longitude=27.48,
            theme="dark",
            public_profile=True,
            searchable=True,
        )
        self.other = User.objects.create_user(
            email="z4-other@makolo.test",
            username="z4-other",
            password=PASSWORD,
            first_name="Autre",
            last_name="Personne",
        )
        UserProfile.objects.create(
            user=self.other,
            profession="Information tierce",
            city="Kinshasa",
            country="CD",
        )

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")

    def test_me_uses_only_request_user_and_rejects_profile_id_override(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(f"/api/v1/me/?profile_id={self.other.pk}")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertIn("profile_id", response.json()["error"]["fields"])

        clean = self.client.get("/api/v1/me/")
        self.assertEqual(clean.status_code, 200)
        self.assertEqual(clean.json()["data"]["identity"]["id"], str(self.user.pk))

    def test_me_identity_is_compact_human_identity_not_account_settings(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["meta"]["projection"], "personal.me")
        self.assertEqual(payload["meta"]["scope"], "personal")
        self.assertEqual(payload["meta"]["schema_version"], 1)

        identity = payload["data"]["identity"]
        self.assertEqual(identity["kind"], "profile")
        self.assertEqual(identity["id"], str(self.user.pk))
        self.assertEqual(identity["display_name"], "Amina Kabongo")
        self.assertEqual(identity["bio"], "Ingénieure et formatrice.")
        self.assertEqual(identity["profession"], "Ingénieure")
        self.assertEqual(identity["location"], {"city": "Lubumbashi", "country": "CD"})
        self.assertEqual(
            identity["presence"],
            {"public_profile": True, "searchable": True},
        )
        self.assertEqual(identity["capabilities"], ["edit_identity"])
        self.assertGreaterEqual(identity["activation"]["percentage"], 0)

        forbidden = {
            "email",
            "phone",
            "birth_date",
            "language",
            "timezone",
            "theme",
            "address",
            "latitude",
            "longitude",
            "notification_preferences",
            "role",
            "permissions",
            "mandates",
        }
        self.assertTrue(forbidden.isdisjoint(identity.keys()))

        serialized = str(payload)
        self.assertNotIn(self.user.email, serialized)
        self.assertNotIn(self.user.phone, serialized)
        self.assertNotIn(self.profile.address, serialized)
        self.assertNotIn(self.other.email, serialized)
        self.assertNotIn("Information tierce", serialized)

    def test_me_and_accounts_auth_me_remain_distinct_contracts(self):
        self.client.force_authenticate(self.user)

        ux_me = self.client.get("/api/v1/me/")
        auth_me = self.client.get("/api/v1/accounts/auth/me/")

        self.assertEqual(ux_me.status_code, 200)
        self.assertEqual(auth_me.status_code, 200)
        self.assertIn("meta", ux_me.json())
        self.assertIn("identity", ux_me.json()["data"])
        self.assertNotIn("email", ux_me.json()["data"]["identity"])

        self.assertNotIn("meta", auth_me.json())
        self.assertEqual(auth_me.json()["email"], self.user.email)

    def test_me_missing_profile_extension_is_stable_and_read_only(self):
        orphan = User.objects.create_user(
            email="z4-orphan@makolo.test",
            username="z4-orphan",
            password=PASSWORD,
        )
        self.assertFalse(UserProfile.objects.filter(user=orphan).exists())
        self.client.force_authenticate(orphan)

        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 200)
        identity = response.json()["data"]["identity"]
        self.assertEqual(identity["display_name"], "z4-orphan")
        self.assertIsNone(identity["profession"])
        self.assertIsNone(identity["location"])
        self.assertEqual(
            identity["presence"],
            {"public_profile": False, "searchable": False},
        )
        self.assertFalse(UserProfile.objects.filter(user=orphan).exists())

    def test_me_links_only_to_real_personal_api_surfaces(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 200)
        links = response.json()["data"]["links"]
        self.assertEqual(links["self"], "/api/v1/me/")
        self.assertEqual(
            links["identity_update"],
            "/api/v1/accounts/auth/profile/update/",
        )
        self.assertEqual(links["considerations"], "/api/v1/me/considerations/")
        self.assertEqual(links["collectives"], "/api/v1/me/collectives/")
        self.assertEqual(links["passport"], "/api/v1/me/passport/")
        self.assertEqual(links["resources"], "/api/v1/me/resources/")
        self.assertEqual(links["partners"], "/api/v1/me/partners/")
