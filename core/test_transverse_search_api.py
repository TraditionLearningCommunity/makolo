from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization


class TransverseSearchBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ts-owner", password="x")
        self.other = User.objects.create_user(username="ts-other", password="x")
        self.scoped = User.objects.create_user(username="ts-scoped", password="x")
        self.space = Organization.objects.create(
            name="Search Space", slug="search-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.visible = Activity.objects.create(
            title="Route visible", space=self.space, created_by=self.owner,
        )
        self.secret = Activity.objects.create(
            title="Route interdite", space=self.space, created_by=self.owner,
        )
        grant_activity_role(
            profile=self.scoped, activity=self.visible,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER, granted_by=self.owner,
        )
        self.client = APIClient()

    def test_personal_search_is_beneficiary_scoped_and_empty_query_is_empty(self):
        Journey.objects.create(
            initiated_by=self.other, beneficiary=self.owner,
            activity=self.visible, status=JourneyStatus.FULFILLED,
            workflow=WorkflowKind.REGISTRATION,
        )
        Journey.objects.create(
            initiated_by=self.other, beneficiary=self.other,
            activity=self.secret, status=JourneyStatus.FULFILLED,
            workflow=WorkflowKind.REGISTRATION,
        )
        self.client.force_authenticate(self.owner)
        url = "/api/v1/me/search/"
        self.assertEqual(self.client.get(url).json()["data"]["items"], [])
        payload = self.client.get(url, {"q": "Route"}).json()["data"]
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["coverage"]["state"], "partial")
        self.assertNotIn("interdite", str(payload).lower())
        self.assertEqual(
            self.client.get(url, {"profile_id": str(self.other.pk)}).status_code, 400
        )

    def test_space_search_does_not_leak_activity_or_count(self):
        self.client.force_authenticate(self.scoped)
        url = "/api/v1/organizations/workspaces/search-space/search/"
        payload = self.client.get(url, {"q": "Route"}).data
        self.assertEqual(payload["page"]["count"], 1)
        self.assertIn("Route visible", str(payload))
        self.assertNotIn("interdite", str(payload).lower())
        forbidden = self.client.get(url, {"q": "interdite"}).data
        self.assertEqual(forbidden["page"]["count"], 0)
        self.assertEqual(forbidden["items"], [])
        self.assertEqual(self.client.get(url).data["items"], [])
        self.assertEqual(self.client.get(url, {"limit": 51}).status_code, 400)

    def test_contexts_never_mix_and_activity_only_is_not_global(self):
        self.client.force_authenticate(self.scoped)
        self.assertEqual(
            self.client.get("/api/v1/me/search/", {"q": "visible"}).json()["data"]["items"],
            [],
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(
                "/api/v1/organizations/workspaces/search-space/search/",
                {"q": "Route"},
            ).status_code,
            404,
        )
