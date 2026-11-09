"""L6: server source scopes, volatile Live and mandate withdrawal.

These tests describe owner behavior; they do not assert that an offline cache
is an authorization. Client cache tombstones are tested in Flutter.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization


User = get_user_model()


class OccurrenceContinuityL6Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="l6-owner", email="l6-owner@example.test",
        )
        self.agent = User.objects.create_user(
            username="l6-scanner", email="l6-scanner@example.test",
        )
        self.outsider = User.objects.create_user(
            username="l6-outsider", email="l6-outsider@example.test",
        )
        self.space = Organization.objects.create(
            name="L6 organisation", slug="l6-org", created_by=self.owner,
        )
        self.other = Organization.objects.create(
            name="Autre organisation", slug="l6-other", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Formation terrain", created_by=self.owner, space=self.space,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity, label="Session du jour",
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
            live_enabled=True,
        )
        self.mandate = grant_activity_role(
            profile=self.agent, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=self.owner,
        )
        self.url = f"/api/v1/operations/occurrences/{self.occurrence.pk}/experience"

    def test_personal_projection_binds_viewer_occurrence_and_live_window(self):
        self.client.force_login(self.agent)
        day = self.client.get(f"{self.url}/day-of/")
        self.assertEqual(day.status_code, 200)
        data = day.json()["data"]
        self.assertEqual(data["identity"]["id"], str(self.occurrence.pk))
        self.assertEqual(data["context"]["viewer_profile_id"], str(self.agent.pk))
        self.assertIsNone(data["context"]["actor_space_id"])
        self.assertEqual(data["surface"], "day_of")
        self.assertTrue(data["live"]["available"])
        self.assertEqual(data["live"]["ends_at"], self.occurrence.end_at.isoformat())
        self.assertIn("no-store", day["Cache-Control"])

        live = self.client.get(f"{self.url}/live/")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["data"]["surface"], "live")
        self.assertEqual(live.json()["data"]["context"]["viewer_profile_id"], str(self.agent.pk))
        self.assertIn("no-store", live["Cache-Control"])

    def test_space_scope_must_match_real_owner_and_member_authority(self):
        self.client.force_login(self.agent)
        included = self.client.get(f"{self.url}/day-of/?actor_space={self.space.pk}")
        self.assertEqual(included.status_code, 200)
        data = included.json()["data"]
        self.assertEqual(data["context"]["actor_space_id"], str(self.space.pk))
        self.assertEqual(data["context"]["viewer_profile_id"], str(self.agent.pk))

        foreign = self.client.get(f"{self.url}/day-of/?actor_space={self.other.pk}")
        self.assertEqual(foreign.status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(f"{self.url}/day-of/?actor_space={self.space.pk}").status_code,
            404,
        )

    def test_revoke_is_authoritative_for_day_of_live_and_web(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(f"{self.url}/day-of/").status_code, 200)
        self.assertEqual(self.client.get(f"{self.url}/live/").status_code, 200)
        personal_page = self.client.get(
            f"/me/occurrences/{self.occurrence.pk}/day-of/",
        )
        self.assertEqual(personal_page.status_code, 200)
        self.assertIn("no-store", personal_page["Cache-Control"])

        revoke_mandate(mandate=self.mandate, actor=self.owner)
        self.assertEqual(self.client.get(f"{self.url}/day-of/").status_code, 404)
        self.assertEqual(self.client.get(f"{self.url}/live/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/me/occurrences/{self.occurrence.pk}/day-of/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/spaces/{self.space.slug}/occurrences/{self.occurrence.pk}/day-of/",
            ).status_code,
            404,
        )

    def test_live_opt_out_only_withdraws_live_not_day_of(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(f"{self.url}/live/").status_code, 200)
        self.occurrence.live_enabled = False
        self.occurrence.save(update_fields=["live_enabled", "updated_at"])
        self.assertEqual(self.client.get(f"{self.url}/live/").status_code, 404)
        day = self.client.get(f"{self.url}/day-of/")
        self.assertEqual(day.status_code, 200)
        self.assertFalse(day.json()["data"]["live"]["available"])
        self.assertNotIn("live", day.json()["data"]["links"])

    def test_space_private_web_pages_are_never_cached(self):
        self.client.force_login(self.agent)
        response = self.client.get(
            f"/spaces/{self.space.slug}/occurrences/{self.occurrence.pk}/day-of/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "data-occurrence-revalidate")
