from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from organizations.models import Organization
from sharing.models import PassportSnapshot, PublicIdentifier


User = get_user_model()


class PassportPublicIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="naomi-demo",
            password="Strong-Passport-Test-2026!",
            first_name="Naomi",
            last_name="Traore",
            bio="Entrepreneure à Goma.",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            profession="Entrepreneure",
            city="Goma",
            country="CD",
        )
        self.space_owner = User.objects.create_user(
            username="space-owner-demo",
            password="Strong-Passport-Test-2026!",
        )
        UserProfile.objects.create(user=self.space_owner)
        self.space = Organization.objects.create(
            name="Mulykap Demo",
            slug="mulykap-demo",
            description="Transport et mobilité.",
            city="Lubumbashi",
            country="CD",
            created_by=self.space_owner,
        )

    def test_profile_and_space_defaults_are_public_and_searchable(self):
        self.assertTrue(self.profile.public_profile)
        self.assertTrue(self.profile.searchable)
        self.assertTrue(self.space.public_profile)
        self.assertTrue(self.space.searchable)

    def test_public_identifier_registry_tracks_profile_and_space(self):
        self.assertEqual(PublicIdentifier.objects.get(profile=self.user).identifier, "naomi-demo")
        self.assertEqual(PublicIdentifier.objects.get(space=self.space).identifier, "mulykap-demo")

    def test_short_public_profile_route_is_anonymous_and_uses_passport(self):
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "naomi-demo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passeport Makolo")
        self.assertContains(response, "Naomi Traore")
        self.assertContains(response, "Entrepreneure")
        self.assertNotContains(response, "QR de vérification")
        self.assertIsNone(response.context["passport_snapshot"])
        self.assertNotContains(response, "Ownership Activity")
        self.assertNotContains(response, "Credential Trust")

    def test_short_public_space_route_is_anonymous_and_professional(self):
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "mulykap-demo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mulykap Demo")
        self.assertContains(response, "Transport et mobilité.")
        self.assertContains(response, "Espace générique")
        self.assertNotContains(response, "QR de vérification")
        self.assertIsNone(response.context["passport_snapshot"])

    def test_non_searchable_profile_returns_404_even_with_known_identifier(self):
        self.profile.searchable = False
        self.profile.save(update_fields=["searchable", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "naomi-demo"}))
        self.assertEqual(response.status_code, 404)

    def test_non_searchable_space_returns_404_even_with_known_identifier(self):
        self.space.searchable = False
        self.space.save(update_fields=["searchable", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "mulykap-demo"}))
        self.assertEqual(response.status_code, 404)

    def test_rendered_passport_issues_verifiable_snapshot(self):
        response = self.client.get(
            reverse("public-passport", kwargs={"identifier": "naomi-demo"}),
            {"document": "1"},
        )
        snapshot = response.context["passport_snapshot"]
        self.assertIsInstance(snapshot, PassportSnapshot)
        self.assertEqual(snapshot.public_identifier, "naomi-demo")
        self.assertEqual(len(snapshot.payload_hash), 64)

        verification = self.client.get(response.context["passport_verification_url"])
        self.assertEqual(verification.status_code, 200)
        self.assertContains(verification, "Document Makolo authentique")
        self.assertContains(verification, snapshot.document_id)
        self.assertContains(verification, snapshot.payload_hash)

    def test_invalid_verification_token_returns_404(self):
        response = self.client.get(
            reverse("sharing:passport-verify", kwargs={"token": "not-a-valid-makolo-document"})
        )
        self.assertEqual(response.status_code, 404)

    def test_public_identifier_namespace_rejects_profile_space_collision(self):
        with self.assertRaises(ValidationError):
            Organization.objects.create(
                name="Collision Demo",
                slug="naomi-demo",
                created_by=self.space_owner,
            )

    def test_snapshot_core_is_immutable(self):
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "naomi-demo"}))
        snapshot = response.context["passport_snapshot"]
        snapshot.public_identifier = "changed"
        with self.assertRaises(ValidationError):
            snapshot.save()
