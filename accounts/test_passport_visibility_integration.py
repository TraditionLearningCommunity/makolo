from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import ProfileVisibilityAudience, ProfileVisibilityPolicy, UserProfile
from accounts.profile_visibility import ProfileVisibilityResolver, replace_profile_visibility
from groups.models import Group, GroupMembership, GroupMembershipStatus
from sharing.passport import PASSPORT_PUBLIC, build_profile_passport
from topics.models import ProfileInterest, ProfileOpenTo, Topic


class PassportVisibilityIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="privacy-owner-a",
            first_name="Amina", last_name="Privée",
            bio="Texte confidentiel", email="secret@example.test",
        )
        self.viewer = User.objects.create_user(username="privacy-viewer-b")
        self.outsider = User.objects.create_user(username="privacy-outsider-c")
        UserProfile.objects.create(user=self.owner, public_profile=True, searchable=True,
                                   profession="Architecte", city="Lubumbashi")
        self.topic = Topic.objects.create(code="privacy-engineering", label="Génie")
        self.interest = ProfileInterest.objects.create(
            profile=self.owner, topic=self.topic, is_public=False,
        )
        self.open_to = ProfileOpenTo.objects.create(
            profile=self.owner, kind="mentor", is_public=False, is_active=True,
        )
        self.endpoint = reverse("personal-projections:passport-visibility")

    def _public(self, viewer=None):
        return build_profile_passport(
            self.owner, variant=PASSPORT_PUBLIC, viewer=viewer,
        )

    def test_existing_private_topic_stays_private_until_explicitly_granted(self):
        self.assertEqual(len(self._public().interests), 0)
        self.assertEqual(len(self._public(self.viewer).interests), 0)
        replace_profile_visibility(
            owner=self.owner, target_kind="interest", interest=self.interest,
            audiences=[{"kind": "public"}],
        )
        self.assertEqual(len(self._public().interests), 1)

    def test_name_can_be_hidden_but_identifier_remains(self):
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="name", audiences=[],
        )
        identity = self._public().identity
        self.assertEqual(identity["name"], self.owner.username)
        self.assertEqual(identity["identifier"], self.owner.username)
        self.assertNotIn("Amina", str(identity))
        self.assertNotIn(self.owner.email, str(identity))

    def test_restricted_profession_is_visible_to_chosen_profile_not_strangers(self):
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="profession",
            audiences=[{"kind": "selected_profile", "id": str(self.viewer.pk)}],
        )
        self.assertEqual(self._public().identity["profession"], "")
        self.assertEqual(self._public(self.outsider).identity["profession"], "")
        self.assertEqual(self._public(self.viewer).identity["profession"], "Architecte")

    def test_collectives_with_zero_memberships_are_empty_then_dynamic(self):
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="bio",
            audiences=[{"kind": "my_collectives"}],
        )
        self.assertEqual(self._public(self.viewer).identity["bio"], "")
        group = Group.objects.create(name="Club Études", owner_profile=self.owner)
        GroupMembership.objects.create(group=group, profile=self.viewer)
        self.assertEqual(self._public(self.viewer).identity["bio"], "")
        GroupMembership.objects.create(group=group, profile=self.owner)
        self.assertEqual(self._public(self.viewer).identity["bio"], "Texte confidentiel")
        membership = GroupMembership.objects.get(group=group, profile=self.viewer)
        membership.status = GroupMembershipStatus.LEFT
        membership.save()
        self.assertEqual(self._public(self.viewer).identity["bio"], "")

    def test_chosen_collective_and_person_are_additive(self):
        group = Group.objects.create(name="Association", owner_profile=self.owner)
        GroupMembership.objects.create(group=group, profile=self.owner)
        GroupMembership.objects.create(group=group, profile=self.viewer)
        replace_profile_visibility(
            owner=self.owner, target_kind="interest", interest=self.interest,
            audiences=[
                {"kind": "selected_group", "id": str(group.pk)},
                {"kind": "selected_profile", "id": str(self.outsider.pk)},
            ],
        )
        self.assertEqual(len(self._public().interests), 0)
        self.assertEqual(len(self._public(self.viewer).interests), 1)
        self.assertEqual(len(self._public(self.outsider).interests), 1)
        self.assertEqual(len(self._public().open_to), 0)

    def test_cannot_choose_a_foreign_collective(self):
        group = Group.objects.create(name="Privé", owner_profile=self.outsider)
        with self.assertRaises(Exception):
            replace_profile_visibility(
                owner=self.owner, target_kind="field", field_key="bio",
                audiences=[{"kind": "selected_group", "id": str(group.pk)}],
            )
        self.assertFalse(
            ProfileVisibilityPolicy.objects.filter(owner=self.owner, field_key="bio").exists()
        )

    def test_owner_endpoint_requires_auth_and_rejects_foreign_interest(self):
        self.assertIn(self.client.get(self.endpoint).status_code, (401, 403))
        self.client.force_login(self.owner)
        data = self.client.get(self.endpoint)
        self.assertEqual(data.status_code, 200)
        self.assertIn("fields", data.json()["data"])
        self.assertEqual(self.client.put(
            self.endpoint, data={
                "target_kind": "interest", "target_id": str(self.interest.pk),
                "audiences": [{"kind": "my_collectives"}],
            }, content_type="application/json",
        ).status_code, 200)
        self.assertEqual(ProfileVisibilityAudience.objects.count(), 1)
        self.client.force_login(self.viewer)
        attempt = self.client.put(
            self.endpoint, data={
                "target_kind": "interest", "target_id": str(self.interest.pk),
                "audiences": [{"kind": "public"}],
            }, content_type="application/json",
        )
        self.assertEqual(attempt.status_code, 404)

    def test_owner_complete_does_not_lose_private_facts(self):
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="bio", audiences=[],
        )
        from sharing.passport import PASSPORT_COMPLETE
        complete = build_profile_passport(self.owner, variant=PASSPORT_COMPLETE)
        self.assertEqual(complete.identity["bio"], "Texte confidentiel")
        self.assertEqual(len(complete.interests), 1)
