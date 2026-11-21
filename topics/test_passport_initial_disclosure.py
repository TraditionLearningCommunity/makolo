"""Passport step 4: consent at creation is not overridden by older editors."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    ProfileVisibilityAudienceKind, ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind,
)
from accounts.profile_visibility import ProfileVisibilityResolver
from topics.models import ProfileInterest, ProfileOpenTo, Topic


class PassportInitialDisclosureTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="stage4-privacy-owner",
        )
        self.topic = Topic.objects.create(
            code="stage4-disclosure", label="Confidentialité étape 4",
        )
        self.client.force_login(self.owner)

    def test_web_interest_may_be_private_from_its_first_save(self):
        url = reverse("account:interests")
        response = self.client.post(
            url, {"topics": [str(self.topic.pk)]},
        )
        self.assertRedirects(response, url)
        row = ProfileInterest.objects.get(profile=self.owner, topic=self.topic)
        self.assertFalse(row.is_public)
        self.assertFalse(ProfileVisibilityResolver(owner=self.owner).interest(row))

    def test_web_interest_may_be_explicitly_public_from_its_first_save(self):
        url = reverse("account:interests")
        response = self.client.post(
            url, {
                "topics": [str(self.topic.pk)],
                "public_topics": [str(self.topic.pk)],
            },
        )
        self.assertRedirects(response, url)
        row = ProfileInterest.objects.get(profile=self.owner, topic=self.topic)
        self.assertTrue(row.is_public)

    def test_web_open_to_can_be_private_without_enabling_search(self):
        url = reverse("account:open-to")
        response = self.client.post(url, {"kinds": ["mentor"]})
        self.assertRedirects(response, url)
        row = ProfileOpenTo.objects.get(profile=self.owner, kind="mentor")
        self.assertFalse(row.is_public)
        self.assertFalse(row.is_searchable)

    def test_existing_passport_public_rule_is_withdrawn_from_topics_editor(self):
        row = ProfileInterest.objects.create(
            profile=self.owner, topic=self.topic, is_public=True,
        )
        policy = ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.INTEREST,
            interest=row,
        )
        policy.audiences.create(kind=ProfileVisibilityAudienceKind.PUBLIC)
        self.client.post(
            reverse("account:interests"),
            {"topics": [str(self.topic.pk)]},
        )
        self.assertFalse(policy.audiences.exists())
        row.refresh_from_db()
        self.assertFalse(row.is_public)
        self.assertFalse(ProfileVisibilityResolver(owner=self.owner).interest(row))

    def test_restricted_passport_rule_is_not_wiped_by_public_checkbox(self):
        other = get_user_model().objects.create_user(
            username="stage4-designated-viewer",
        )
        row = ProfileInterest.objects.create(
            profile=self.owner, topic=self.topic, is_public=False,
        )
        policy = ProfileVisibilityPolicy.objects.create(
            owner=self.owner,
            target_kind=ProfileVisibilityTargetKind.INTEREST,
            interest=row,
        )
        policy.audiences.create(
            kind=ProfileVisibilityAudienceKind.SELECTED_PROFILE,
            selected_profile=other,
        )
        self.client.post(
            reverse("account:interests"),
            {"topics": [str(self.topic.pk)]},
        )
        self.assertTrue(policy.audiences.filter(
            kind=ProfileVisibilityAudienceKind.SELECTED_PROFILE,
        ).exists())
        self.assertFalse(ProfileVisibilityResolver(owner=self.owner).interest(row))
        self.assertTrue(
            ProfileVisibilityResolver(owner=self.owner, viewer=other).interest(row)
        )

    def test_api_first_save_visibility_is_explicit_and_does_not_turn_on_search(self):
        url = reverse("personal-projections:consideration-settings")
        response = self.client.put(
            url,
            data={
                "family": "interests",
                "values": [str(self.topic.pk)],
                "new_visibility": "private",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        interest = ProfileInterest.objects.get(profile=self.owner, topic=self.topic)
        self.assertFalse(interest.is_public)

        response = self.client.put(
            url,
            data={
                "family": "open_to",
                "values": ["mentor"],
                "new_visibility": "private",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        opening = ProfileOpenTo.objects.get(profile=self.owner, kind="mentor")
        self.assertFalse(opening.is_public)
        self.assertFalse(opening.is_searchable)

        response = self.client.put(
            url,
            data={
                "family": "interests",
                "values": [str(self.topic.pk)],
                "new_visibility": "public",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        interest.refresh_from_db()
        self.assertFalse(interest.is_public, "An existing private choice is retained")

    def test_invalid_visibility_does_not_create_a_declaration(self):
        response = self.client.put(
            reverse("personal-projections:consideration-settings"),
            data={
                "family": "interests",
                "values": [str(self.topic.pk)],
                "new_visibility": "everyone",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProfileInterest.objects.filter(
            profile=self.owner,
        ).exists())
