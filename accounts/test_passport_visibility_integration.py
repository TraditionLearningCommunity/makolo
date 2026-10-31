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
        group = Group.objects.create(name="Club Études", owner_profile=self.outsider)
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

    def test_authenticated_collective_view_only_expands_live_html_not_export(self):
        group = Group.objects.create(name="Forum professionnel", owner_profile=self.owner)
        GroupMembership.objects.create(group=group, profile=self.viewer)
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="bio",
            audiences=[{"kind": "my_collectives"}],
        )
        public_url = reverse(
            "sharing:passport-profile", kwargs={"profile_id": self.owner.pk},
        )
        anon = self.client.get(public_url)
        self.assertEqual(anon.status_code, 200)
        self.assertNotContains(anon, "Texte confidentiel")
        self.client.force_login(self.viewer)
        still_public = self.client.get(public_url)
        self.assertEqual(still_public.status_code, 200)
        self.assertNotContains(still_public, "Texte confidentiel")
        visible = self.client.get(public_url, {"audience": "mine"})
        self.assertEqual(visible.status_code, 200)
        self.assertContains(visible, "Texte confidentiel")
        exported = self.client.get(public_url, {"audience": "mine", "download": "1"})
        self.assertEqual(exported.status_code, 200)
        self.assertNotContains(exported, "Texte confidentiel")

    def test_web_visibility_editor_is_owner_scoped(self):
        url = reverse("sharing:passport-visibility")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {
            "target_kind": "field",
            "target_id": "profession",
            "audience": ["my_collectives"],
        })
        self.assertEqual(response.status_code, 302)
        policy = ProfileVisibilityPolicy.objects.get(owner=self.owner, field_key="profession")
        self.assertEqual(list(policy.audiences.values_list("kind", flat=True)), ["my_collectives"])
        self.client.force_login(self.viewer)
        self.client.post(url, {
            "target_kind": "field",
            "target_id": "profession",
            "audience": ["public"],
        })
        policy.refresh_from_db()
        self.assertEqual(list(policy.audiences.values_list("kind", flat=True)), ["my_collectives"])

    def test_company_and_organization_follow_independent_disclosure(self):
        profile = UserProfile.objects.get(user=self.owner)
        profile.company_name = "Atelier personnel"
        profile.organization_name = "Association déclarée"
        profile.save(update_fields=["company_name", "organization_name"])
        replace_profile_visibility(
            owner=self.owner, target_kind="field",
            field_key="company_name", audiences=[],
        )
        anonymous = self._public()
        self.assertEqual(anonymous.identity["company_name"], "")
        self.assertEqual(anonymous.identity["organization_name"], "Association déclarée")
        replace_profile_visibility(
            owner=self.owner, target_kind="field",
            field_key="company_name",
            audiences=[{"kind": "selected_profile", "id": str(self.viewer.pk)}],
        )
        self.assertEqual(self._public(self.viewer).identity["company_name"], "Atelier personnel")
        self.assertEqual(self._public(self.outsider).identity["company_name"], "")
        from sharing.passport_documents import serialize_passport_projection
        payload = serialize_passport_projection(self._public())
        self.assertEqual(payload["identity"]["company_name"], "")
        self.assertEqual(payload["identity"]["organization_name"], "Association déclarée")

    def test_owner_complete_includes_groups_without_exposing_them_publicly(self):
        group = Group.objects.create(name="Collectif personnel", owner_profile=self.owner)
        complete = build_profile_passport(self.owner, variant="complete")
        self.assertIn("Collectif personnel", [row["name"] for row in complete.group_affiliations])
        public = self._public()
        self.assertEqual(public.group_affiliations, ())
        from sharing.passport_documents import serialize_passport_projection
        self.assertEqual(serialize_passport_projection(public)["group_affiliations"], [])

    def test_malformed_privacy_target_returns_400_without_server_error(self):
        self.client.force_login(self.owner)
        response = self.client.put(
            self.endpoint, data={
                "target_kind": "interest", "target_id": "not-a-uuid",
                "audiences": [{"kind": "public"}],
            }, content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_public_verification_hides_old_personal_content_after_privacy_revocation(self):
        from sharing.passport_documents import (
            issue_passport_snapshot, passport_verification_token,
        )
        snapshot = issue_passport_snapshot(self._public())
        verification = reverse("sharing:passport-verify", kwargs={
            "token": passport_verification_token(snapshot),
        })
        before = self.client.get(verification)
        self.assertEqual(before.status_code, 200)
        self.assertTrue(before.context["can_view_dated_passport"])
        replace_profile_visibility(
            owner=self.owner, target_kind="field", field_key="bio",
            audiences=[],
        )
        after = self.client.get(verification)
        self.assertEqual(after.status_code, 200)
        self.assertTrue(after.context["snapshot_intact"])
        self.assertFalse(after.context["can_view_dated_passport"])
        self.assertEqual(after.context["dated_payload"], {})
        self.assertNotContains(after, "Texte confidentiel")
