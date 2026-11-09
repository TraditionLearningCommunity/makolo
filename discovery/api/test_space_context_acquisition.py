"""Space actor acquisition reuses Discovery without inheriting personal authority."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization


class DiscoverySpaceAcquisitionTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="discovery-space-viewer", email="space-viewer@test.local")
        self.outsider = User.objects.create_user(username="discovery-space-outsider", email="space-outsider@test.local")
        self.space = Organization.objects.create(
            name="Discovery Space", slug="discovery-space", created_by=self.viewer,
        )
        self.other_space = Organization.objects.create(
            name="Other Space", slug="other-discovery-space", created_by=self.outsider,
        )
        grant_space_role(
            profile=self.viewer, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.viewer,
        )
        grant_space_role(
            profile=self.outsider, space=self.other_space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.outsider,
        )
        activity = Activity.objects.create(
            space=self.space, created_by=self.viewer,
            title="Discovery Space published activity",
            short_description="A publicly available activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        start = timezone.now() + timedelta(days=3)
        Occurrence.objects.create(
            activity=activity, start_at=start, end_at=start + timedelta(hours=2),
            timezone="Africa/Lubumbashi", status=OccurrenceStatus.SCHEDULED,
        )
        other_activity = Activity.objects.create(
            space=self.space, created_by=self.viewer,
            title="Discovery Space second published activity",
            short_description="Second public activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        Occurrence.objects.create(
            activity=other_activity, start_at=start + timedelta(days=1),
            end_at=start + timedelta(days=1, hours=2),
            timezone="Africa/Lubumbashi", status=OccurrenceStatus.SCHEDULED,
        )
        self.client = APIClient()
        self.items_url = reverse("discovery_api:items")
        self.space_url = f"/api/v1/organizations/workspaces/{self.space.slug}/discover/"

    def _space_query(self, **additional):
        return {"context": "space", "space": self.space.slug, **additional}

    def test_guest_and_personal_contracts_remain_unchanged(self):
        public = self.client.get(self.items_url)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data["data"]["surface"], "discover_public")
        self.client.force_authenticate(self.viewer)
        personal = self.client.get(self.items_url)
        self.assertEqual(personal.status_code, 200)
        self.assertEqual(personal.data["data"]["surface"], "discover_me")

    def test_space_context_reuses_shared_collection_with_read_only_items(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.items_url, self._space_query())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta"]["scope"], "space")
        data = response.data["data"]
        self.assertEqual(data["surface"], "discover_space")
        self.assertEqual(data["actor"], {"type": "space", "id": str(self.space.pk)})
        self.assertEqual(data["viewer"], {"type": "profile", "id": str(self.viewer.pk)})
        self.assertTrue(data["items"], data)
        for item in data["items"]:
            self.assertEqual(item["capabilities"], ["view"])
            self.assertEqual(item["saved"]["state"], "unknown")
            self.assertNotIn("saved", item["links"])
            self.assertEqual(item["engagement"]["capabilities"], [])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_space_route_reuses_same_items_not_a_second_selection(self):
        self.client.force_authenticate(self.viewer)
        shared = self.client.get(self.items_url, self._space_query(q="published"))
        direct = self.client.get(self.space_url, {"q": "published"})
        self.assertEqual(direct.status_code, 200, direct.data)
        self.assertEqual(
            [i["identity"]["candidate_key"] for i in direct.data["items"]],
            [i["identity"]["candidate_key"] for i in shared.data["data"]["items"]],
        )
        self.assertEqual(direct.data["actor"], shared.data["data"]["actor"])

    def test_guest_and_unauthorized_space_are_rejected_without_fallback(self):
        guest = self.client.get(self.items_url, self._space_query())
        self.assertIn(guest.status_code, {401, 403})
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.items_url, self._space_query()).status_code, 404)
        self.assertEqual(self.client.get(self.space_url).status_code, 404)

    def test_invalid_context_and_client_profile_override_are_rejected(self):
        self.client.force_authenticate(self.viewer)
        for params in (
            {"space": self.space.slug},
            {"context": "space"},
            {"context": "unknown"},
            {"context": "space", "space": self.space.slug, "profile_id": str(self.outsider.pk)},
        ):
            self.assertEqual(self.client.get(self.items_url, params).status_code, 400)

    def test_space_endpoint_rejects_conflicting_actor_parameters(self):
        self.client.force_authenticate(self.viewer)
        for params in (
            {"context": "personal"},
            {"space": self.other_space.slug},
            {"profile_id": str(self.outsider.pk)},
        ):
            self.assertEqual(self.client.get(self.space_url, params).status_code, 400)

    def test_space_endpoint_returns_400_for_invalid_cursor(self):
        self.client.force_authenticate(self.viewer)
        result = self.client.get(self.space_url, {"continuation": "invalid"})
        self.assertEqual(result.status_code, 400)

    def test_map_details_do_not_expose_personal_action_handoffs(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(
            reverse("discovery_api:map"),
            self._space_query(spatial="1", details="1"),
        )
        self.assertEqual(response.status_code, 200, response.data)
        for item in response.data["results"]:
            self.assertEqual(item["capabilities"], ["view"])
            self.assertEqual(item["engagement"]["capabilities"], [])

    def test_web_space_list_pagination_uses_signed_continuation(self):
        from urllib.parse import quote

        self.client.force_login(self.viewer)
        web_url = reverse(
            "organizations:space-discover", kwargs={"slug": self.space.slug},
        )
        first = self.client.get(web_url, {"page_size": 1})
        self.assertEqual(first.status_code, 200)
        token = first.context["next_continuation"]
        self.assertTrue(token)
        self.assertContains(first, "continuation=" + quote(token, safe=""))
        second = self.client.get(
            web_url,
            {"page_size": 1, "page": 2, "continuation": token},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.context["page_obj"].number, 2)
        self.assertNotEqual(
            first.context["discovery_cards"][0].candidate_key,
            second.context["discovery_cards"][0].candidate_key,
        )
        self.assertEqual(
            self.client.get(
                reverse("discovery:home"),
                {"page_size": 1, "page": 2, "continuation": token},
            ).context["search_errors"] != [],
            True,
        )

    def test_web_space_query_context_never_falls_back_to_personal(self):
        self.client.force_login(self.viewer)
        personal_url = reverse("discovery:home")
        response = self.client.get(
            personal_url,
            {"context": "space", "space": self.space.slug, "q": "published"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(
            reverse("organizations:space-discover", kwargs={"slug": self.space.slug})
        ))
        self.assertIn("q=published", response["Location"])
        self.assertNotIn("context=space", response["Location"])
        self.assertEqual(
            self.client.get(personal_url, {"context": "space"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("organizations:space-discover", kwargs={"slug": self.space.slug}),
                {"context": "personal"},
            ).status_code,
            404,
        )

    def test_pagination_correction_marker_does_not_invalidate_cursor(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(
            self.items_url,
            self._space_query(page_size=1, _correction="client-presentational"),
        )
        self.assertEqual(first.status_code, 200)
        token = first.data["data"]["continuation"]["token"]
        self.assertTrue(token)
        second = self.client.get(
            self.items_url,
            self._space_query(page_size=1, continuation=token),
        )
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["data"]["page"], 2)

    def test_revoked_member_loses_list_map_and_detail_space_authority(self):
        from django.test import Client
        from authorization.services import revoke_mandate

        member = User.objects.create_user(
            username="discovery-revoked-member",
            email="discovery-revoked@test.local",
        )
        mandate = grant_space_role(
            profile=member, space=self.space,
            role=SystemRoleCode.SPACE_ADMIN, granted_by=self.viewer,
        )
        self.client.force_authenticate(member)
        initial = self.client.get(self.items_url, self._space_query())
        self.assertEqual(initial.status_code, 200, initial.data)
        self.assertTrue(initial.data["data"]["items"])
        item = initial.data["data"]["items"][0]["identity"]
        detail_url = reverse("discovery_api:item-detail", kwargs={
            "family": item["family"], "item_id": item["resource"]["id"],
        })
        self.assertEqual(
            self.client.get(detail_url, self._space_query()).status_code, 200,
        )

        revoke_mandate(mandate=mandate, actor=self.viewer)
        self.assertEqual(
            self.client.get(self.items_url, self._space_query()).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("discovery_api:map"), self._space_query(spatial="1")
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(detail_url, self._space_query()).status_code,
            404,
        )
        web = Client()
        web.force_login(member)
        self.assertEqual(
            web.get(reverse(
                "organizations:space-discover", kwargs={"slug": self.space.slug},
            )).status_code,
            404,
        )

    def test_signed_cursor_is_bound_to_space_and_viewer(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(self.items_url, self._space_query(page_size=1))
        self.assertEqual(first.status_code, 200, first.data)
        token = first.data["data"]["continuation"]["token"]
        self.assertTrue(token, first.data["data"])
        second_context = self.client.get(
            self.items_url, self._space_query(page_size=1, continuation=token),
        )
        self.assertEqual(second_context.status_code, 200, second_context.data)
        personal = self.client.get(
            self.items_url, {"page_size": 1, "continuation": token},
        )
        self.assertEqual(personal.status_code, 400)
        changed_space = self.client.get(
            self.items_url, {"context": "space", "space": self.other_space.slug,
                             "page_size": 1, "continuation": token},
        )
        self.assertEqual(changed_space.status_code, 404)
