from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.forms import AccountProfileForm
from accounts.models import UserProfile


User = get_user_model()
PASSWORD = "Strong-G1-Profile-Password-2026!"


class G1ProfileDefaultsTests(TestCase):
    def test_new_profile_is_private_and_incomplete_by_default(self):
        user = User.objects.create_user(
            username="g1-defaults",
            email="g1-defaults@example.test",
            password=PASSWORD,
        )
        profile = UserProfile.objects.create(user=user)

        self.assertFalse(profile.public_profile)
        self.assertFalse(profile.searchable)
        self.assertFalse(profile.profile_completed)

    def test_profile_completion_is_derived_from_compatible_minimum(self):
        user = User.objects.create_user(
            username="g1-completion",
            email="g1-completion@example.test",
            password=PASSWORD,
            first_name="Sarah",
            last_name="Makolo",
        )
        profile = UserProfile.objects.create(user=user)
        self.assertFalse(profile.derive_profile_completed())

        profile.city = "Lubumbashi"
        self.assertTrue(profile.derive_profile_completed())


class G1ProfileSectionFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="g1-sections",
            email="g1-sections@example.test",
            password=PASSWORD,
            first_name="Sarah",
            last_name="Makolo",
            bio="Bio existante",
            website="https://example.test",
            linkedin_url="https://linkedin.com/in/example",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            profession="Ingénieure",
            country="CD",
            city="Lubumbashi",
            address="Adresse privée",
            company_name="Ancienne entreprise",
            organization_name="Ancienne organisation",
            public_profile=True,
            searchable=True,
            profile_completed=True,
        )

    def test_link_section_does_not_overwrite_other_sections(self):
        form = AccountProfileForm(
            {
                "website": "https://makolo.example",
                "linkedin_url": "https://linkedin.com/in/sarah",
                "facebook_url": "https://facebook.com/sarah",
                "instagram_url": "https://instagram.com/sarah",
                "tiktok_url": "https://www.tiktok.com/@sarah",
                "x_url": "https://x.com/sarah",
                "youtube_url": "https://youtube.com/@sarah",
            },
            instance=self.user,
            profile=self.profile,
            section="links",
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.tiktok_url, "https://www.tiktok.com/@sarah")
        self.assertEqual(self.user.youtube_url, "https://youtube.com/@sarah")
        self.assertEqual(self.user.bio, "Bio existante")
        self.assertEqual(self.profile.address, "Adresse privée")
        self.assertTrue(self.profile.public_profile)
        self.assertTrue(self.profile.searchable)

    def test_link_section_uses_url_validation(self):
        form = AccountProfileForm(
            {"tiktok_url": "pas-une-url"},
            instance=self.user,
            profile=self.profile,
            section="links",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tiktok_url", form.errors)

    def test_optional_personal_and_contact_fields_can_be_blank(self):
        personal = AccountProfileForm(
            {"first_name": "", "last_name": "", "birth_date": "", "gender": ""},
            instance=self.user,
            profile=self.profile,
            section="personal",
        )
        self.assertTrue(personal.is_valid(), personal.errors)

        contact = AccountProfileForm(
            {"phone": "", "country": "", "city": "", "address": ""},
            instance=self.user,
            profile=self.profile,
            section="contact",
        )
        self.assertTrue(contact.is_valid(), contact.errors)

    def test_privacy_section_does_not_modify_sensitive_data(self):
        original_phone = self.user.phone
        original_address = self.profile.address
        form = AccountProfileForm(
            {"public_profile": "", "searchable": ""},
            instance=self.user,
            profile=self.profile,
            section="privacy",
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.phone, original_phone)
        self.assertEqual(self.profile.address, original_address)
        self.assertFalse(self.profile.public_profile)
        self.assertFalse(self.profile.searchable)


class G1ProfileWebTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="g1-web",
            email="g1-web@example.test",
            password=PASSWORD,
            bio="Présentation existante",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            address="Adresse confidentielle",
            public_profile=False,
            searchable=False,
        )
        self.client.force_login(self.user)

    def test_profile_page_exposes_six_progressive_sections(self):
        response = self.client.get(reverse("account:profile"))
        self.assertEqual(response.status_code, 200)
        for label in (
            "1 · Présentation",
            "2 · Informations personnelles",
            "3 · Coordonnées",
            "4 · Liens & réseaux",
            "5 · Préférences",
            "6 · Confidentialité",
            "TikTok",
            "YouTube",
            "Makolo ne présente pas leur propriété comme vérifiée",
        ):
            self.assertContains(response, label)

    def test_contact_section_updates_only_contact_fields(self):
        response = self.client.post(
            reverse("account:profile"),
            {
                "section": "contact",
                "phone": "+243 999 000 222",
                "country": "CD",
                "city": "Kinshasa",
                "address": "Nouvelle adresse privée",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('account:profile')}#contact")

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.phone, "+243 999 000 222")
        self.assertEqual(self.user.bio, "Présentation existante")
        self.assertEqual(self.profile.city, "Kinshasa")
        self.assertFalse(self.profile.public_profile)
        self.assertFalse(self.profile.searchable)


class G1ProfileApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="g1-api",
            email="g1-api@example.test",
            password=PASSWORD,
            first_name="Sarah",
            last_name="Makolo",
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.url = "/api/v1/accounts/auth/profile/update/"

    def test_profile_update_requires_authentication(self):
        response = self.client.patch(self.url, {"city": "Lubumbashi"}, format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_profile_api_updates_user_and_profile_fields(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            self.url,
            {
                "city": "Lubumbashi",
                "profession": "Ingénieure",
                "tiktok_url": "https://www.tiktok.com/@g1-api",
                "youtube_url": "https://youtube.com/@g1-api",
                "public_profile": True,
                "searchable": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.tiktok_url, "https://www.tiktok.com/@g1-api")
        self.assertEqual(self.user.youtube_url, "https://youtube.com/@g1-api")
        self.assertEqual(self.profile.profession, "Ingénieure")
        self.assertTrue(self.profile.public_profile)
        self.assertTrue(self.profile.searchable)
        self.assertTrue(self.profile.profile_completed)

    def test_profile_api_rejects_invalid_urls(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            self.url,
            {"tiktok_url": "not-a-url"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tiktok_url", response.data)

    def test_profile_completed_cannot_be_forced_by_api(self):
        incomplete = User.objects.create_user(
            username="g1-api-incomplete",
            email="g1-api-incomplete@example.test",
            password=PASSWORD,
        )
        profile = UserProfile.objects.create(user=incomplete)
        self.client.force_authenticate(incomplete)

        response = self.client.patch(
            self.url,
            {"profile_completed": True, "bio": "Une bio"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        profile.refresh_from_db()
        self.assertFalse(profile.profile_completed)




class G1ProfileCompatibilityTests(TestCase):
    def test_legacy_profile_data_remains_compatible(self):
        user = User.objects.create_user(
            username="g1-legacy",
            email="g1-legacy@example.test",
            password=PASSWORD,
        )

        profile = UserProfile.objects.create(
            user=user,
            company_name="Legacy Co",
            organization_name="Legacy Org",
            public_profile=True,
            searchable=True,
            profile_completed=True,
        )

        profile.refresh_from_db()

        self.assertEqual(profile.company_name, "Legacy Co")
        self.assertEqual(profile.organization_name, "Legacy Org")
        self.assertTrue(profile.public_profile)
        self.assertTrue(profile.searchable)
        self.assertTrue(profile.profile_completed)

    def test_new_profile_defaults_are_private(self):
        user = User.objects.create_user(
            username="g1-new",
            email="g1-new@example.test",
            password=PASSWORD,
        )

        profile = UserProfile.objects.create(user=user)

        self.assertFalse(profile.public_profile)
        self.assertFalse(profile.searchable)
