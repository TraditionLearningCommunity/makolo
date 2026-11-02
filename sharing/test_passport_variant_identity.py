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

    def test_unselected_custom_bio_stays_excluded_but_identity_stays(self):
        custom = build_profile_passport(self.owner, variant="custom")
        self.assertEqual(custom.identity["name"], self.owner.full_name)
        self.assertEqual(custom.identity["avatar_url"],
                         "/media/variant-public-photo.jpg")
        self.assertEqual(custom.identity["bio"], "")
