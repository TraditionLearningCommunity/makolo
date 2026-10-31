from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import (
    PROFILE_VISIBILITY_FIELDS,
    ProfileVisibilityAudience,
    ProfileVisibilityAudienceKind,
    ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind,
)
from topics.models import ProfileInterest, ProfileOpenTo, Topic


class ProfileVisibilityPolicyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="privacy-owner")
        self.other = User.objects.create_user(username="privacy-other")
        self.topic = Topic.objects.create(code="privacy-topic", label="Confidentialité")

    def test_publishable_fields_are_allowlisted_and_identity_handle_is_not_hideable(self):
        self.assertIn("name", PROFILE_VISIBILITY_FIELDS)
        self.assertIn("profession", PROFILE_VISIBILITY_FIELDS)
        for sensitive in ("email", "phone", "birth_date", "address", "latitude", "longitude", "username"):
            self.assertNotIn(sensitive, PROFILE_VISIBILITY_FIELDS)

        policy = ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="profession",
        )
        self.assertEqual(policy.owner, self.owner)
        with self.assertRaises(ValidationError):
            ProfileVisibilityPolicy.objects.create(
                owner=self.owner,
                target_kind=ProfileVisibilityTargetKind.FIELD,
                field_key="email",
            )

    def test_one_policy_per_owner_and_field(self):
        ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="name",
        )
        with self.assertRaises(ValidationError):
            ProfileVisibilityPolicy.objects.create(
                owner=self.owner,
                target_kind=ProfileVisibilityTargetKind.FIELD,
                field_key="name",
            )
        ProfileVisibilityPolicy.objects.create(
            owner=self.other,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="name",
        )

    def test_interest_and_open_to_targets_preserve_canonical_ownership(self):
        interest = ProfileInterest.objects.create(profile=self.owner, topic=self.topic)
        open_to = ProfileOpenTo.objects.create(
            profile=self.owner,
            kind="collaborate",
            topic=self.topic,
        )
        for kind, target in (
            (ProfileVisibilityTargetKind.INTEREST, {"interest": interest}),
            (ProfileVisibilityTargetKind.OPEN_TO, {"open_to": open_to}),
        ):
            policy = ProfileVisibilityPolicy.objects.create(
                owner=self.owner, target_kind=kind, **target
            )
            self.assertEqual(policy.owner, self.owner)
            with self.assertRaises(ValidationError):
                ProfileVisibilityPolicy.objects.create(
                    owner=self.other, target_kind=kind, **target
                )

    def test_private_policy_has_no_audiences_and_multi_audience_is_additive(self):
        policy = ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="city",
        )
        self.assertFalse(policy.audiences.exists())

        ProfileVisibilityAudience.objects.create(
            policy=policy,
            kind=ProfileVisibilityAudienceKind.MY_COLLECTIVES,
        )
        ProfileVisibilityAudience.objects.create(
            policy=policy,
            kind=ProfileVisibilityAudienceKind.SELECTED_PROFILE,
            selected_profile=self.other,
        )
        self.assertEqual(
            set(policy.audiences.values_list("kind", flat=True)),
            {"my_collectives", "selected_profile"},
        )
        # "Mes collectifs" is an audience selector, not a materialized list:
        # no Group or Team membership needs to exist when it is selected.
        with self.assertRaises(ValidationError):
            ProfileVisibilityAudience.objects.create(
                policy=policy, kind=ProfileVisibilityAudienceKind.MY_COLLECTIVES
            )

    def test_audience_kind_cannot_reference_a_different_target_shape(self):
        policy = ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.FIELD,
            field_key="bio",
        )
        with self.assertRaises(ValidationError):
            ProfileVisibilityAudience.objects.create(
                policy=policy,
                kind=ProfileVisibilityAudienceKind.PUBLIC,
                selected_profile=self.other,
            )
        with self.assertRaises(ValidationError):
            ProfileVisibilityAudience.objects.create(
                policy=policy,
                kind=ProfileVisibilityAudienceKind.SELECTED_GROUP,
            )
        ProfileVisibilityAudience.objects.create(
            policy=policy,
            kind=ProfileVisibilityAudienceKind.PUBLIC,
        )

    def test_unrelated_legacy_visibility_flags_are_unchanged(self):
        interest = ProfileInterest.objects.create(profile=self.owner, topic=self.topic, is_public=False)
        open_to = ProfileOpenTo.objects.create(
            profile=self.owner, kind="mentor", topic=self.topic, is_public=False
        )
        self.assertFalse(interest.is_public)
        self.assertFalse(open_to.is_public)
        ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.INTEREST,
            interest=interest,
        )
        interest.refresh_from_db()
        open_to.refresh_from_db()
        self.assertFalse(interest.is_public)
        self.assertFalse(open_to.is_public)
