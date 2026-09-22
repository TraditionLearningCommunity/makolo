from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import Access, AccessStatus
from access.services import issue_access, render_access_credential
from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from commerce.models import CommerceOrder, PaymentMode
from journeys.models import Journey, JourneyStatus, WorkflowKind


PASSWORD = "Makolo!2026-Z6-AccessA7"


class Z6PersonalAccessAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = self._user("z6-access-owner", "Amina", "Kabongo")
        self.other = self._user("z6-access-other", "Benoît", "Mulumba")
        self.outsider = self._user("z6-access-outsider", "Chantal", "Ilunga")
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            title="Voyage Z6",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.mine = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="z6:mine",
        )
        self.historical = Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.USED,
            source_key="z6:history",
        )
        self.foreign = issue_access(
            beneficiary=self.outsider,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="z6:foreign",
        )

        self.bought_journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.CONFIRMED,
        )
        CommerceOrder.objects.create(
            journey=self.bought_journey,
            buyer=self.owner,
            payment_mode=PaymentMode.NONE,
            currency="USD",
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("0.00"),
        )
        self.bought = issue_access(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.bought_journey,
            source_key="z6:bought",
        )

    def _user(self, username, first_name, last_name):
        return User.objects.create_user(
            username=username,
            email=f"{username}@makolo.test",
            password=PASSWORD,
            first_name=first_name,
            last_name=last_name,
        )

    def test_accesses_require_authentication_and_reject_profile_override(self):
        response = self.client.get("/api/v1/me/accesses/")
        self.assertEqual(response.status_code, 401)

        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/me/accesses/?profile_id={self.other.pk}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_default_collection_is_only_current_beneficiary_accesses(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/accesses/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["projection"], "personal.accesses")
        self.assertEqual(payload["meta"]["scope"], "personal")
        self.assertEqual(payload["data"]["relationship"], "beneficiary")

        ids = [row["identity"]["id"] for row in payload["data"]["items"]]
        self.assertEqual(ids, [str(self.mine.pk)])
        self.assertNotIn(str(self.historical.pk), ids)
        self.assertNotIn(str(self.bought.pk), ids)
        self.assertNotIn(str(self.foreign.pk), ids)

        row = payload["data"]["items"][0]
        self.assertEqual(row["relationship"], "beneficiary")
        self.assertEqual(row["state"]["code"], AccessStatus.VALID)
        self.assertEqual(row["activity"]["id"], str(self.activity.pk))
        self.assertEqual(row["occurrence"]["id"], str(self.occurrence.pk))
        self.assertIsNone(row["holder"])
        self.assertTrue(row["credential"]["available"])
        self.assertTrue(row["credential"]["presentable"])
        self.assertEqual(row["capabilities"], ["present_credential"])
        self.assertEqual(
            row["links"]["credential"],
            f"/api/v1/me/accesses/{self.mine.pk}/credential/",
        )

        rendered = str(payload)
        credential = self.mine.credentials.get()
        self.assertNotIn(str(credential.public_id), rendered)
        self.assertNotIn(render_access_credential(credential), rendered)
        self.assertNotIn(self.outsider.email, rendered)

    def test_purchased_for_other_is_explicit_and_does_not_expose_private_journey(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            "/api/v1/me/accesses/?relationship=purchased_for_other"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["relationship"], "purchased_for_other")
        self.assertEqual(payload["page"]["count"], 1)

        row = payload["items"][0]
        self.assertEqual(row["identity"]["id"], str(self.bought.pk))
        self.assertEqual(row["relationship"], "purchased_for_other")
        self.assertEqual(
            row["holder"],
            {"kind": "profile", "display_name": "Benoît Mulumba"},
        )
        self.assertIsNone(row["journey"])
        serialized = str(row)
        self.assertNotIn(self.other.email, serialized)
        self.assertNotIn(str(self.bought_journey.pk), serialized)

    def test_search_and_pagination_are_bounded_inside_personal_scope(self):
        second_activity = Activity.objects.create(
            title="Atelier distinct Z6",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        second = issue_access(
            beneficiary=self.owner,
            activity=second_activity,
            source_key="z6:second",
        )

        self.client.force_authenticate(self.owner)
        page = self.client.get("/api/v1/me/accesses/?limit=1&offset=1")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["data"]["page"]["count"], 2)
        self.assertEqual(len(page.json()["data"]["items"]), 1)

        search = self.client.get("/api/v1/me/accesses/?q=Atelier")
        self.assertEqual(search.status_code, 200)
        self.assertEqual(
            [item["identity"]["id"] for item in search.json()["data"]["items"]],
            [str(second.pk)],
        )

        invalid = self.client.get("/api/v1/me/accesses/?limit=51")
        self.assertEqual(invalid.status_code, 400)
        invalid_relation = self.client.get(
            "/api/v1/me/accesses/?relationship=owner"
        )
        self.assertEqual(invalid_relation.status_code, 400)

    def test_credential_depth_is_protected_no_store_and_never_in_collection(self):
        self.client.force_authenticate(self.owner)
        credential = self.mine.credentials.get()
        response = self.client.get(
            f"/api/v1/me/accesses/{self.mine.pk}/credential/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["meta"]["projection"],
            "personal.access.credential",
        )
        representation = response.json()["data"]["representation"]
        self.assertEqual(
            representation["payload"],
            render_access_credential(credential),
        )
        self.assertEqual(
            representation["credential_type"],
            credential.credential_type,
        )
        self.assertNotIn("public_id", representation)
        self.assertNotIn("version", representation)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

        self.client.force_authenticate(self.outsider)
        denied = self.client.get(
            f"/api/v1/me/accesses/{self.mine.pk}/credential/"
        )
        self.assertEqual(denied.status_code, 404)

    def test_buyer_can_retrieve_only_credential_from_own_purchase_for_other(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/me/accesses/{self.bought.pk}/credential/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["relationship"],
            "purchased_for_other",
        )
        self.assertEqual(
            response.json()["data"]["holder"]["display_name"],
            "Benoît Mulumba",
        )

        self.client.force_authenticate(self.outsider)
        denied = self.client.get(
            f"/api/v1/me/accesses/{self.bought.pk}/credential/"
        )
        self.assertEqual(denied.status_code, 404)

    def test_terminal_access_does_not_reexpose_a_credential_payload(self):
        terminal = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="z6:terminal",
        )
        terminal.status = AccessStatus.REVOKED
        terminal._allow_status_transition = True
        terminal.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/me/accesses/{terminal.pk}/credential/"
        )
        self.assertEqual(response.status_code, 404)

    def test_moi_links_to_secondary_access_surface_without_copying_accesses(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["links"]["accesses"],
            "/api/v1/me/accesses/",
        )
        self.assertNotIn("accesses", response.json()["data"])
