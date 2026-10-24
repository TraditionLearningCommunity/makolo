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

    def test_private_unsearchable_or_inactive_profiles_are_not_exposed(self):
        for changes in (
            {"public_profile": False},
            {"searchable": False},
        ):
            self.profile.public_profile = True
            self.profile.searchable = True
            for field, value in changes.items():
                setattr(self.profile, field, value)
            self.profile.save()
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.profile.public_profile = True
        self.profile.searchable = True
        self.profile.save()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
