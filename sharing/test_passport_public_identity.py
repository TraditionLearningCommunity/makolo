from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        self.assertContains(response, "Organisation")
        self.assertNotContains(response, "QR de vérification")
        self.assertIsNone(response.context["passport_snapshot"])

    def test_private_profile_returns_404_even_with_known_identifier(self):
        self.profile.public_profile = False
        self.profile.save(update_fields=["public_profile", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "naomi-demo"}))
        self.assertEqual(response.status_code, 404)

    def test_private_space_returns_404_even_with_known_identifier(self):
        self.space.public_profile = False
        self.space.save(update_fields=["public_profile", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "mulykap-demo"}))
        self.assertEqual(response.status_code, 404)

    def test_public_profile_not_searchable_remains_accessible_by_direct_link(self):
        self.profile.searchable = False
        self.profile.save(update_fields=["searchable", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "naomi-demo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Naomi Traore")

    def test_public_space_not_searchable_remains_accessible_by_direct_link(self):
        self.space.searchable = False
        self.space.save(update_fields=["searchable", "updated_at"])
        response = self.client.get(reverse("public-passport", kwargs={"identifier": "mulykap-demo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mulykap Demo")

    def test_owner_can_open_private_passport_when_not_searchable(self):
        self.profile.public_profile = False
        self.profile.searchable = False
        self.profile.save(update_fields=["public_profile", "searchable", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("sharing:passport-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["projection"].variant, "complete")

    def test_canonical_identifier_grants_private_variants_to_owner_only(self):
        self.profile.public_profile = False
        self.profile.searchable = False
        self.profile.save(update_fields=["public_profile", "searchable", "updated_at"])
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url, {"variant": "complete"}).status_code, 404)
        self.client.force_login(self.space_owner)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.user)
        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.context["projection"].variant, "public")

        complete = self.client.get(url, {"variant": "complete"})
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.context["projection"].variant, "complete")
        self.assertContains(complete, "Informations personnelles")
        self.assertEqual(complete["Cache-Control"], "private, no-store")

        selected = self.client.get(
            url, {"variant": "custom", "include": "bio"},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.context["projection"].variant, "custom")
        self.assertNotIn("owner_details", selected.context["projection"].identity)

    def test_anonymous_public_variant_cannot_request_owner_content(self):
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})
        self.assertEqual(
            self.client.get(url, {"variant": "complete"}).status_code, 403,
        )
        self.assertEqual(
            self.client.get(url, {"variant": "custom", "include": "bio"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(url, {"variant": "thematic", "topic": "any"}).status_code,
            403,
        )
        self.assertEqual(self.client.get(url, {"variant": "unknown"}).status_code, 404)

    def test_public_identity_only_passport_can_be_issued(self):
        minimal = User.objects.create_user(
            username="passport-only-name",
            password="Strong-Passport-Test-2026!",
        )
        UserProfile.objects.create(user=minimal, public_profile=True)
        url = reverse("public-passport", kwargs={"identifier": "passport-only-name"})
        response = self.client.get(url, {"document": "1"})
        self.assertEqual(response.status_code, 200)
        snapshot = response.context["passport_snapshot"]
        self.assertEqual(snapshot.payload["identity"]["name"], minimal.username)
        self.assertEqual(snapshot.payload["activities"], [])
        self.assertEqual(snapshot.payload["identity"]["owner_details"], {})

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
        self.assertContains(verification, "Version émise par Makolo")
        self.assertContains(verification, snapshot.document_id)
        self.assertContains(verification, snapshot.payload_hash)

    def test_two_issued_versions_retain_their_own_dated_content(self):
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})
        first = self.client.get(url, {"document": "1"})
        first_snapshot = first.context["passport_snapshot"]
        first_link = first.context["passport_verification_url"]

        self.user.bio = "Présentation actualisée après la première émission."
        self.user.save(update_fields=["bio", "updated_at"])
        second = self.client.get(url, {"document": "1"})
        second_snapshot = second.context["passport_snapshot"]
        self.assertNotEqual(first_snapshot.pk, second_snapshot.pk)

        historical = self.client.get(first_link)
        self.assertEqual(historical.status_code, 200)
        self.assertTrue(historical.context["can_view_dated_passport"])
        self.assertContains(historical, "Le Passeport à cette date")
        self.assertContains(historical, "Entrepreneure à Goma.")
        self.assertNotContains(historical, "Présentation actualisée après la première émission.")
        self.assertContains(historical, first_snapshot.document_id)
        self.assertNotContains(historical, second_snapshot.document_id)
        self.assertEqual(historical["Cache-Control"], "private, no-store")

        current = self.client.get(url)
        self.assertContains(current, "Présentation actualisée après la première émission.")
        self.assertNotContains(current, "Entrepreneure à Goma.")

    def test_versions_list_is_private_and_links_to_exact_issued_snapshots(self):
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})
        first = self.client.get(url, {"document": "1"})
        snapshot = first.context["passport_snapshot"]
        history_url = reverse("sharing:passport-me-history")

        anonymous = self.client.get(history_url)
        self.assertIn(anonymous.status_code, (302, 403))
        self.client.force_login(self.space_owner)
        denied = self.client.get(history_url)
        self.assertEqual(denied.status_code, 200)
        self.assertNotContains(denied, snapshot.document_id)

        self.client.force_login(self.user)
        history = self.client.get(history_url)
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, snapshot.document_id)
        from urllib.parse import urlsplit
        self.assertContains(
            history, urlsplit(first.context["passport_verification_url"]).path,
        )
        self.assertEqual(history["Cache-Control"], "private, no-store")

    def test_unpublishing_public_passport_hides_historical_content_from_visitors(self):
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})
        first = self.client.get(url, {"document": "1"})
        signed = first.context["passport_verification_url"]

        self.profile.public_profile = False
        self.profile.save(update_fields=["public_profile", "updated_at"])
        anonymous = self.client.get(signed)
        self.assertEqual(anonymous.status_code, 200)
        self.assertFalse(anonymous.context["can_view_dated_passport"])
        self.assertNotContains(anonymous, "Entrepreneure à Goma.")

        self.client.force_login(self.user)
        owner = self.client.get(signed)
        self.assertTrue(owner.context["can_view_dated_passport"])
        self.assertContains(owner, "Entrepreneure à Goma.")

    def test_revocation_or_integrity_failure_never_serves_historical_content(self):
        url = reverse("public-passport", kwargs={"identifier": "naomi-demo"})
        first = self.client.get(url, {"document": "1"})
        snapshot = first.context["passport_snapshot"]
        signed = first.context["passport_verification_url"]

        snapshot.revoked_at = timezone.now()
        snapshot.save(update_fields=["revoked_at"])
        revoked = self.client.get(signed)
        self.assertFalse(revoked.context["can_view_dated_passport"])
        self.assertContains(revoked, "révoquée")
        self.assertNotContains(revoked, "Entrepreneure à Goma.")

        snapshot.revoked_at = None
        snapshot.save(update_fields=["revoked_at"])
        original_payload = snapshot.payload
        corrupted = {**original_payload, "identity": {
            **original_payload["identity"], "bio": "Texte altéré hors émission",
        }}
        PassportSnapshot.objects.filter(pk=snapshot.pk).update(payload=corrupted)
        invalid = self.client.get(signed)
        self.assertFalse(invalid.context["snapshot_intact"])
        self.assertFalse(invalid.context["can_view_dated_passport"])
        self.assertContains(invalid, "ne correspond pas")
        self.assertNotContains(invalid, "Texte altéré hors émission")

        PassportSnapshot.objects.filter(pk=snapshot.pk).update(
            payload=original_payload, payload_hash="0" * 64,
        )
        invalid_token = self.client.get(signed)
        self.assertEqual(invalid_token.status_code, 404)

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
        response = self.client.get(
            reverse("public-passport", kwargs={"identifier": "naomi-demo"}),
            {"document": "1"},
        )
        snapshot = response.context["passport_snapshot"]
        snapshot.public_identifier = "changed"
        with self.assertRaises(ValidationError):
            snapshot.save()
