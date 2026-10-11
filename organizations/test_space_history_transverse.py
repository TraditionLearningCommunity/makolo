from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus, OccurrenceTimingKind
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus


class SpaceHistoryPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="sh-owner", password="x")
        self.scoped = User.objects.create_user(username="sh-scoped", password="x")
        self.member = User.objects.create_user(username="sh-member", password="x")
        self.space = Organization.objects.create(
            name="History Space", slug="history-space", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space, name="History team", is_active=True,
        )
        TeamMembership.objects.create(
            team=team, user=self.member, status=TeamMembershipStatus.ACTIVE,
        )
        self.activity = Activity.objects.create(
            title="Départ visible", created_by=self.owner, space=self.space,
        )
        self.other_activity = Activity.objects.create(
            title="Départ secret", created_by=self.owner, space=self.space,
        )
        self.grant = grant_activity_role(
            profile=self.scoped, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER, granted_by=self.owner,
        )
        now = timezone.now()
        self.past = Occurrence.objects.create(
            activity=self.activity, label="Voyage passé",
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=2, hours=-2),
            status=OccurrenceStatus.COMPLETED,
        )
        self.secret = Occurrence.objects.create(
            activity=self.other_activity, label="Voyage secret",
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=2, hours=-2),
            status=OccurrenceStatus.COMPLETED,
        )
        self.undated = Occurrence.objects.create(
            activity=self.activity, label="Sans heure de fin historique",
            start_date=(now - timedelta(days=2)).date(),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            status=OccurrenceStatus.COMPLETED,
        )
        self.client = APIClient()
        self.url = "/api/v1/organizations/workspaces/history-space/history/"

    def test_auth_membership_and_other_space_are_not_authority(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_activity_scope_never_exposes_space_wide_history(self):
        self.client.force_authenticate(self.scoped)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        rendered = str(response.data)
        self.assertIn("Voyage passé", rendered)
        self.assertNotIn("Voyage secret", rendered)
        self.assertNotIn(str(self.secret.pk), rendered)
        self.assertEqual(response.data["page"]["count"], 1)
        self.assertEqual(response.data["coverage"]["state"], "partial")

    def test_owner_time_is_not_updated_at_and_unknown_is_not_invented(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["source"]["id"] for row in response.data["items"]}
        self.assertIn(str(self.past.pk), ids)
        self.assertNotIn(str(self.undated.pk), ids)
        row = next(row for row in response.data["items"] if row["source"]["id"] == str(self.past.pk))
        self.assertEqual(datetime.fromisoformat(row["occurred_at"]), self.past.end_at)

    def test_search_pagination_and_invalid_responsibility(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url, {"q": "Voyage", "limit": 1})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["page"]["count"], 2)
        self.assertTrue(response.data["page"]["has_more"])
        second = self.client.get(self.url, {"q": "Voyage", "limit": 1, "offset": 1})
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(
            response.data["items"][0]["source"]["id"],
            second.data["items"][0]["source"]["id"],
        )
        self.assertEqual(self.client.get(self.url, {"limit": 51}).status_code, 400)
        self.assertEqual(
            self.client.get(self.url, {"responsibility": "mandate:invalid"}).status_code,
            404,
        )

    def test_revoked_activity_authority_no_longer_exposes_history(self):
        self.client.force_authenticate(self.scoped)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        revoke_mandate(mandate=self.grant, actor=self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_cancelled_commerce_order_is_visible_only_with_owner_permission(self):
        from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
        from journeys.models import Journey, JourneyStatus, WorkflowKind
        cancelled_at = timezone.now() - timedelta(hours=2)
        buyer = self.member
        journey = Journey.objects.create(
            initiated_by=buyer, beneficiary=buyer, activity=self.activity,
            workflow=WorkflowKind.PURCHASE, status=JourneyStatus.CANCELLED,
        )
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=buyer,
            payee_space=self.space,
            payment_mode=PaymentMode.NONE,
            status=CommerceOrderStatus.CANCELLED,
            cancelled_at=cancelled_at,
        )
        self.client.force_authenticate(self.owner)
        owner_history = self.client.get(self.url)
        self.assertEqual(owner_history.status_code, 200)
        matching = [
            item for item in owner_history.data["items"]
            if item["source"]["kind"] == "commerce_order"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["source"]["id"], str(order.pk))
        self.assertEqual(matching[0]["occurred_at"], cancelled_at.isoformat())
        self.assertNotIn(buyer.username, str(owner_history.data))
        from django.urls import reverse
        self.client.force_login(self.owner)
        web = self.client.get(reverse(
            "organizations:space-retrieval-order-detail",
            kwargs={"slug": self.space.slug, "order_id": order.pk},
        ))
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, order.reference)
        self.client.force_authenticate(self.scoped)
        scoped = self.client.get(self.url)
        self.assertEqual(scoped.status_code, 200)
        self.assertNotIn(str(order.pk), str(scoped.data))
        self.assertNotIn("commerce_order", scoped.data["coverage"]["owners"])

    def test_space_web_owner_depth_is_checked_before_display(self):
        from django.urls import reverse

        occurrence_url = reverse(
            "organizations:space-retrieval-occurrence-detail",
            kwargs={"slug": self.space.slug, "occurrence_id": self.past.pk},
        )
        secret_url = reverse(
            "organizations:space-retrieval-occurrence-detail",
            kwargs={"slug": self.space.slug, "occurrence_id": self.secret.pk},
        )
        activity_url = reverse(
            "organizations:space-retrieval-activity-detail",
            kwargs={"slug": self.space.slug, "activity_id": self.activity.pk},
        )
        self.client.force_login(self.scoped)
        response = self.client.get(occurrence_url, {"responsibility": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voyage passé")
        self.assertEqual(self.client.get(secret_url).status_code, 404)
        self.assertEqual(self.client.get(
            reverse(
                "organizations:space-retrieval-activity-detail",
                kwargs={"slug": self.space.slug, "activity_id": self.other_activity.pk},
            ),
        ).status_code, 404)
        self.assertEqual(self.client.get(activity_url).status_code, 200)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(occurrence_url).status_code, 404)

    def test_space_history_web_grouped_result_restores_period_and_selection(self):
        from django.urls import reverse

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("organizations:space-history", kwargs={"slug": self.space.slug}),
            {"q": "Voyage", "kind": "occurrence",
             "from": "2026-01-01", "to": "2026-12-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voyage passé")
        self.assertContains(response, "Depuis")
        self.assertContains(response, "Jusqu’au")
        self.assertContains(response, "selected=occurrence%3A")
