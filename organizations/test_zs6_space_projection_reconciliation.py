from uuid import UUID

from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import (
    Organization,
    Team,
    TeamMembership,
    TeamMembershipStatus,
)


class ZS6SpaceProjectionReconciliationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs6-owner", email="zs6-owner@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="zs6-outsider", email="zs6-outsider@test.local", password="x"
        )
        self.team_only = User.objects.create_user(
            username="zs6-team", email="zs6-team@test.local", password="x"
        )
        self.platform_only = User.objects.create_user(
            username="zs6-platform", email="zs6-platform@test.local", password="x"
        )
        self.activity_actor = User.objects.create_user(
            username="zs6-activity", email="zs6-activity@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS6 Space",
            slug="zs6-space",
            created_by=self.owner,
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Activity A",
            slug="zs6-activity-a",
            created_by=self.owner,
            space=self.space,
        )
        self.activity_mandate = grant_activity_role(
            profile=self.activity_actor,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="Équipe ZS6",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.team_only,
            status=TeamMembershipStatus.ACTIVE,
        )
        grant_platform_role(
            profile=self.platform_only,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform_only,
        )
        self.client = APIClient()

    def _url(self, suffix):
        return f"/api/v1/organizations/workspaces/{self.space.slug}/{suffix}/"

    def test_now_and_discover_are_honest_bounded_contracts(self):
        self.client.force_authenticate(self.owner)
        for suffix in ("now", "discover"):
            response = self.client.get(self._url(suffix))
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["items"], [])
            self.assertFalse(response.data["has_more"])
            self.assertEqual(response.data["selection"]["state"], "unavailable")
            self.assertEqual(
                response.data["selection"]["reason"],
                "no_safe_selection_contract",
            )
            serialized = str(response.data).lower()
            for forbidden in (
                "score",
                "rank",
                "relevance",
                "probability",
                "accesscredential",
                "private_key",
                "api_token",
                "qr_token",
            ):
                self.assertNotIn(forbidden, serialized)
            self.assertEqual(
                response["Cache-Control"],
                "private, no-store",
            )

    def test_now_and_discover_authority_matrix(self):
        for suffix in ("now", "discover"):
            anonymous = self.client.get(self._url(suffix))
            self.assertIn(anonymous.status_code, {401, 403})

        for actor in (self.outsider, self.team_only, self.platform_only):
            self.client.force_authenticate(actor)
            for suffix in ("now", "discover"):
                self.assertEqual(self.client.get(self._url(suffix)).status_code, 404)

        self.client.force_authenticate(self.activity_actor)
        for suffix in ("now", "discover"):
            response = self.client.get(self._url(suffix))
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["authority"]["scope"], "activity_limited")
            self.assertTrue(response.data["authority"]["limited_to_activities"])

    def test_responsibility_lens_is_revalidated_and_never_authority(self):
        self.client.force_authenticate(self.activity_actor)
        own = self.client.get(
            self._url("now"),
            {"responsibility": f"mandate:{self.activity_mandate.pk}"},
        )
        self.assertEqual(own.status_code, 200, own.data)
        self.assertEqual(
            own.data["responsibility"],
            f"mandate:{self.activity_mandate.pk}",
        )

        foreign_space = Organization.objects.create(
            name="ZS6 Foreign",
            slug="zs6-foreign",
            created_by=self.owner,
        )
        foreign_mandate = grant_space_role(
            profile=self.activity_actor,
            space=foreign_space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        foreign = self.client.get(
            self._url("now"),
            {"responsibility": f"mandate:{foreign_mandate.pk}"},
        )
        self.assertEqual(foreign.status_code, 404)

        malformed = self.client.get(
            self._url("now"),
            {"responsibility": "space_owner"},
        )
        self.assertEqual(malformed.status_code, 404)

    def test_revoked_mandate_removes_projection_access(self):
        self.client.force_authenticate(self.activity_actor)
        before = self.client.get(self._url("now"))
        self.assertEqual(before.status_code, 200, before.data)
        revoke_mandate(mandate=self.activity_mandate, actor=self.owner)
        after = self.client.get(self._url("now"))
        self.assertEqual(after.status_code, 404)

    def test_final_zs_routes_are_mounted_without_shadowing(self):
        expected = {
            "now": "workspace-now",
            "discover": "workspace-discover",
            "work": "workspace-work",
            "us": "workspace-us",
            "relationships": "workspace-relationships",
            "pilot": "workspace-pilot",
            "mark": "workspace-mark",
        }
        for suffix, url_name in expected.items():
            path = self._url(suffix)
            self.assertEqual(resolve(path).url_name, url_name)
            self.assertEqual(
                reverse(f"organizations_api:{url_name}", kwargs={"slug": self.space.slug}),
                path,
            )

        occurrence_id = UUID("00000000-0000-0000-0000-000000000001")
        day_of = f"/api/v1/operations/occurrences/{occurrence_id}/day-of/"
        live = f"/api/v1/operations/occurrences/{occurrence_id}/live/"
        scanner = f"/api/v1/scanner/occurrences/{occurrence_id}/context/"
        self.assertEqual(resolve(day_of).url_name, "occurrence-day-of")
        self.assertEqual(resolve(live).url_name, "occurrence-live")
        self.assertEqual(resolve(scanner).url_name, "occurrence-context")
