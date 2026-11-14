"""N3 Discovery stays one owner projection, but never merges actor authority."""

from datetime import timedelta
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import (
    Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus,
)
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization


class DiscoveryContextualDetailTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            username="n3-viewer", email="n3-viewer@test.local",
        )
        self.outsider = User.objects.create_user(
            username="n3-outsider", email="n3-outsider@test.local",
        )
        self.space = Organization.objects.create(
            name="N3 Space", slug="n3-space", created_by=self.viewer,
        )
        grant_space_role(
            profile=self.viewer, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.viewer,
        )
        self.activity = Activity.objects.create(
            title="Possibilité N3 publiée",
            slug="n3-published-activity",
            created_by=self.viewer,
            space=self.space,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        start = timezone.now() + timedelta(days=7)
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=start,
            end_at=start + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.url = reverse(
            "discovery_api:item-detail",
            kwargs={"family": "activity", "item_id":self.activity.pk},
        )
        self.web_url = reverse(
            "discovery:possibility-detail",
            kwargs={"family": "activity", "item_id":self.activity.pk},
        )
        self.client = APIClient()

    def _space_query(self):
        return {"context": "space", "space": self.space.slug}

    def _make_journey(self, beneficiary, *, status=JourneyStatus.IN_PROGRESS):
        return Journey.objects.create(
            activity=self.activity,
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            workflow=WorkflowKind.REGISTRATION,
            status=status,
        )

    def test_guest_detail_remains_public_without_private_journey_relation(self):
        self._make_journey(self.viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta"]["scope"], "public")
        self.assertNotIn("journey_continuation", response.data["data"]["item"])

    def test_opening_personal_detail_does_not_create_a_journey(self):
        self.client.force_authenticate(self.viewer)
        before = Journey.objects.count()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta"]["scope"], "personal")
        self.assertNotIn("journey_continuation", response.data["data"]["item"])
        self.assertEqual(Journey.objects.count(), before)

    def test_only_beneficiary_gets_real_existing_journey_handoff(self):
        outsider_journey = self._make_journey(self.outsider)
        self.client.force_authenticate(self.viewer)
        detail = self.client.get(self.url)
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertNotIn("journey_continuation", detail.data["data"]["item"])

        own_journey = self._make_journey(self.viewer)
        detail = self.client.get(self.url)
        self.assertEqual(detail.status_code, 200, detail.data)
        continuation = detail.data["data"]["item"]["journey_continuation"]
        self.assertEqual(continuation["state"], "active")
        self.assertEqual(continuation["resource"]["id"], str(own_journey.pk))
        self.assertEqual(continuation["links"]["native"], f"/journeys/{own_journey.pk}")
        self.assertEqual(
            continuation["links"]["web"],
            reverse("core:participant-journey-detail", kwargs={"pk": own_journey.pk}),
        )
        self.assertNotEqual(continuation["resource"]["id"], str(outsider_journey.pk))

    def test_finished_personal_journey_is_viewable_but_not_resumable(self):
        journey = self._make_journey(self.viewer, status=JourneyStatus.FULFILLED)
        self.client.force_authenticate(self.viewer)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        continuation = result.data["data"]["item"]["journey_continuation"]
        self.assertEqual(continuation["state"], "finished")
        self.assertEqual(continuation["label"], "Voir ma démarche")
        self.assertEqual(continuation["resource"]["id"], str(journey.pk))

    def test_space_detail_is_same_endpoint_with_read_only_space_actor(self):
        self._make_journey(self.viewer)
        self.client.force_authenticate(self.viewer)
        result = self.client.get(self.url, self._space_query())
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["meta"]["scope"], "space")
        self.assertEqual(result.data["data"]["actor"], {
            "type": "space", "id": str(self.space.pk),
        })
        self.assertEqual(result.data["data"]["viewer"]["id"], str(self.viewer.pk))
        item = result.data["data"]["item"]
        self.assertEqual(item["capabilities"], ["view"])
        self.assertEqual(item["engagement"]["capabilities"], [])
        self.assertEqual(item["saved"]["state"], "unknown")
        self.assertNotIn("journey_continuation", item)
        self.assertNotIn("saved", item["links"])
        self.assertNotIn("web_saved", item["links"])

    def test_space_parameter_cannot_trigger_personal_save_mutation(self):
        saved_url = reverse(
            "discovery_api:item-saved",
            kwargs={"family": "activity", "item_id": self.activity.pk},
        ) + "?" + urlencode(self._space_query())
        self.client.force_authenticate(self.viewer)
        put = self.client.put(saved_url)
        delete = self.client.delete(saved_url)
        self.assertEqual(put.status_code, 400)
        self.assertEqual(delete.status_code, 400)

    def test_forged_or_revoked_space_context_never_falls_back_to_personal(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url, self._space_query()).status_code, 404)
        self.client.force_authenticate(None)
        self.assertIn(
            self.client.get(self.url, self._space_query()).status_code, {401, 403},
        )
        self.client.force_authenticate(self.viewer)
        for params in (
            {"space": self.space.slug},
            {"context": "space"},
            {"context": "space", "space": self.space.slug, "profile_id": str(self.outsider.pk)},
        ):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)

    def test_web_n3_reuses_same_detail_and_does_not_expose_personal_space_actions(self):
        journey = self._make_journey(self.viewer)
        self.client.force_login(self.viewer)
        personal = self.client.get(self.web_url)
        self.assertEqual(personal.status_code, 200)
        self.assertContains(personal, "Reprendre ma démarche")
        self.assertContains(
            personal,
            reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
        )
        collective = self.client.get(
            self.web_url + "?" + urlencode(self._space_query()),
        )
        self.assertEqual(collective.status_code, 200)
        self.assertTrue(collective.context["discovery_space"])
        self.assertContains(collective, "Possibilité N3 publiée")
        self.assertContains(collective, 'data-mk-runtime-scope="space:')
        self.assertNotContains(collective, "Reprendre ma démarche")
        self.assertNotContains(collective, "J’enregistre")
        self.assertNotContains(collective, "Créer Journey")
        self.assertEqual(Journey.objects.count(), 1)

    def test_space_listing_points_to_the_same_contextual_web_detail(self):
        self.client.force_login(self.viewer)
        listing = self.client.get(
            reverse("organizations:space-discover", kwargs={"slug": self.space.slug}),
        )
        self.assertEqual(listing.status_code, 200)
        self.assertContains(
            listing,
            self.web_url + "?context=space&amp;space=" + self.space.slug,
        )

    def test_web_space_detail_rejects_unauthorized_actor(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.web_url + "?" + urlencode(self._space_query()))
        self.assertEqual(response.status_code, 404)
