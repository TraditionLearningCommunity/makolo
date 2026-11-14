"""Personal Passport identity is stable across the four presentation variants."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from sharing.passport import build_profile_passport


class PassportVariantIdentityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="variant-identity",
            first_name="Maya",
            last_name="Exemple",
            phone="+243810000000",
            bio="Présentation facultative",
        )
        self.owner.metadata = {"avatar_url": "/media/variant-public-photo.jpg"}
        self.owner.save(update_fields=["metadata", "updated_at"])
        UserProfile.objects.create(
            user=self.owner, public_profile=True, searchable=False,
        )

    def test_identity_is_not_a_theme_or_an_optional_custom_activity(self):
        for variant in ("public", "thematic", "custom"):
            with self.subTest(variant=variant):
                projection = build_profile_passport(
                    self.owner, variant=variant, topic_codes=(),
                )
                self.assertEqual(projection.identity["name"], "Maya Exemple")
                self.assertEqual(projection.identity["avatar_url"],
                                 "/media/variant-public-photo.jpg")
                self.assertNotIn("owner_details", projection.identity)
                self.assertNotIn("+243810000000", str(projection.identity))

    def test_complete_keeps_sensitive_details_separate_from_public(self):
        complete = build_profile_passport(self.owner, variant="complete")
        public = build_profile_passport(self.owner, variant="public")
        self.assertEqual(complete.identity["owner_details"]["phone"],
                         "+243810000000")
        self.assertEqual(public.identity["name"], complete.identity["name"])
        self.assertNotIn("owner_details", public.identity)
        self.assertFalse(public.team_affiliations)

    def test_public_personal_details_survive_all_variants_with_field_permissions(self):
        from accounts.profile_visibility import replace_profile_visibility

        row = self.owner.profile
        row.city = "Lubumbashi"
        row.country = "CD"
        row.save(update_fields=["city", "country", "updated_at"])
        full = build_profile_passport(self.owner, variant="complete")
        self.assertEqual(full.identity["owner_details"]["phone"], "+243810000000")

        for variant in ("public", "thematic", "custom"):
            with self.subTest(variant=variant):
                details = build_profile_passport(
                    self.owner, variant=variant,
                ).identity["presentation_details"]
                self.assertEqual(details["first_name"], "Maya")
                self.assertEqual(details["last_name"], "Exemple")
                self.assertEqual(details["username"], "variant-identity")
                self.assertEqual(details["city"], "Lubumbashi")
                self.assertEqual(details["country"], "CD")
                self.assertNotIn("phone", details)
                self.assertNotIn("birth_date", details)

        replace_profile_visibility(
            owner=self.owner, target_kind="field",
            field_key="name", audiences=[],
        )
        replace_profile_visibility(
            owner=self.owner, target_kind="field",
            field_key="city", audiences=[],
        )
        details = build_profile_passport(
            self.owner, variant="public",
        ).identity["presentation_details"]
        self.assertEqual(details, {
            "username": "variant-identity", "country": "CD",
        })

        # Custom excludes location without changing the canonical facts.
        custom = build_profile_passport(
            self.owner, variant="custom",
            excluded_sections=["location"],
        )
        self.assertEqual(custom.identity["presentation_details"], {
            "username": "variant-identity",
        })

    def test_custom_location_baseline_excludes_a_private_city(self):
        from accounts.models import ProfileVisibilityTargetKind
        from accounts.profile_visibility import replace_profile_visibility

        row = self.owner.profile
        row.city = "Ville confidentielle"
        row.country = "CD"
        row.save(update_fields=["city", "country", "updated_at"])
        replace_profile_visibility(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="city",
            audiences=[],
        )
        custom = build_profile_passport(self.owner, variant="custom")
        self.assertEqual(custom.identity["location"], "CD")
        self.assertNotIn("Ville confidentielle", str(custom.identity))

    def test_personalized_starts_with_public_facts_and_explicitly_excludes(self):
        default = build_profile_passport(self.owner, variant="custom")
        self.assertEqual(default.identity["name"], self.owner.full_name)
        self.assertEqual(default.identity["avatar_url"],
                         "/media/variant-public-photo.jpg")
        self.assertEqual(default.identity["bio"], "Présentation facultative")

        excluded = build_profile_passport(
            self.owner, variant="custom", selected_sections=["identity"],
        )
        self.assertEqual(excluded.identity["name"], self.owner.full_name)
        self.assertEqual(excluded.identity["avatar_url"], "")
        self.assertEqual(excluded.identity["bio"], "")
