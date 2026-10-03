from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from topics.models import OpenToKind, ProfileInterest, ProfileOpenTo, Topic
from topics.services import replace_profile_open_to

User = get_user_model()
PASSWORD = "Strong-G3-Password-2026!"


class G3PublicProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="g3-public",
            email="g3-public@example.test",
            password=PASSWORD,
            first_name="Amina",
            last_name="Makolo",
            bio="Bio publique",
            phone="+243999000111",
            website="https://example.test",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            city="Lubumbashi",
            address="Adresse secrète",
            latitude=-11.66,
            longitude=27.48,
            public_profile=False,
            searchable=False,
        )
        self.url = reverse("account:public-profile", kwargs={"profile_id": self.user.pk})

    def test_legacy_public_profile_route_is_hidden_when_not_public_or_searchable(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile", "updated_at"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.profile.public_profile = False
        self.profile.searchable = True
        self.profile.save(update_fields=["public_profile", "searchable", "updated_at"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_legacy_public_profile_route_redirects_to_canonical_passport(self):
        self.profile.public_profile = True
        self.profile.searchable = True
        self.profile.save(update_fields=["public_profile", "searchable", "updated_at"])

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("public-passport", kwargs={"identifier": self.user.username}),
        )


class G3OpenToTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username="g3-a", email="g3-a@example.test", password=PASSWORD)
        self.b = User.objects.create_user(username="g3-b", email="g3-b@example.test", password=PASSWORD)

    def test_create_modify_remove_open_to(self):
        replace_profile_open_to(profile=self.a, kinds=[OpenToKind.MENTOR], public_kinds=[OpenToKind.MENTOR])
        row = ProfileOpenTo.objects.get(profile=self.a)
        self.assertTrue(row.is_public)
        self.assertFalse(row.is_searchable)
        replace_profile_open_to(profile=self.a, kinds=[OpenToKind.MENTOR], searchable_kinds=[OpenToKind.MENTOR])
        row.refresh_from_db()
        self.assertFalse(row.is_public)
        self.assertTrue(row.is_searchable)
        replace_profile_open_to(profile=self.a, kinds=[])
        self.assertFalse(ProfileOpenTo.objects.filter(profile=self.a).exists())

    def test_user_a_cannot_modify_b_through_settings_view(self):
        ProfileOpenTo.objects.create(profile=self.b, kind=OpenToKind.COLLABORATE, is_public=True)
        self.client.force_login(self.a)
        response = self.client.post(reverse("account:open-to"), {"kinds": [OpenToKind.ORGANIZE], "public_kinds": [OpenToKind.ORGANIZE]})
        self.assertRedirects(response, reverse("account:open-to"))
        self.assertTrue(ProfileOpenTo.objects.filter(profile=self.b, kind=OpenToKind.COLLABORATE, is_public=True).exists())
        self.assertTrue(ProfileOpenTo.objects.filter(profile=self.a, kind=OpenToKind.ORGANIZE).exists())
