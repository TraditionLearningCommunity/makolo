from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile


class PublicProfileAPITests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="native-public-owner",
            first_name="Amina",
            last_name="Test",
            bio="Présentation publique",
            phone="+243999000111",
            email="private-profile@example.test",
        )
        self.profile = UserProfile.objects.create(
            user=self.owner,
            public_profile=True,
            searchable=True,
            city="Lubumbashi",
            address="Ne jamais exposer",
        )
        self.url = f"/api/v1/accounts/public-profiles/{self.owner.pk}/"

    def test_anonymous_sees_only_canonical_public_identity(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        profile = response.json()["data"]["profile"]
        self.assertEqual(profile["kind"], "profile")
        self.assertEqual(profile["id"], str(self.owner.pk))
        self.assertEqual(profile["name"], "Amina Test")
        self.assertEqual(profile["bio"], "Présentation publique")
        self.assertNotIn("email", profile)
        self.assertNotIn("phone", profile)
        self.assertNotIn("address", profile)

    def test_unsearchable_profile_remains_directly_accessible_but_private_is_hidden(self):
        self.profile.searchable = False
        self.profile.save(update_fields=["searchable", "updated_at"])
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.profile.public_profile = False
        self.profile.save(update_fields=["public_profile", "updated_at"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile", "updated_at"])
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
