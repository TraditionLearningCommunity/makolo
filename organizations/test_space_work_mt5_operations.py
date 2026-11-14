"""MT5: transport N3 actions are owner-confirmed, scoped and separately authorized."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from capacity.models import CapacityPool
from organizations.models import Organization, SpaceArchetype
from transport.models import TransportDeparture, TransportRoute, TransportService, Vehicle


class MT5DepartureOperationsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mt5-operation-owner", password="x")
        self.outsider = User.objects.create_user(username="mt5-operation-other", password="x")
        self.space = Organization.objects.create(
            name="Transport MT5", slug="mt5-operating-space",
            created_by=self.owner, archetype=SpaceArchetype.TRANSPORT_OPERATOR,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Ligne interurbaine", space=self.space,
            created_by=self.owner, status="published",
        )
        self.mandate = grant_activity_role(
            profile=self.owner, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        self.route = TransportRoute.objects.create(
            name="Lubumbashi–Kolwezi", space=self.space,
        )
        TransportService.objects.create(activity=self.activity, route=self.route)
        self.occurrence = Occurrence.objects.create(
            activity=self.activity, label="Départ de matin",
            start_at=timezone.now() + timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            label="Passagers", total_quantity=12,
        )
        self.departure = TransportDeparture.objects.create(
            occurrence=self.occurrence, passenger_capacity_pool=pool,
        )
        self.vehicle = Vehicle.objects.create(
            space=self.space, label="Bus 20", passenger_capacity=20,
        )
        self.client.force_login(self.owner)
        self.api_url = reverse(
            "organizations_api:workspace-work-g3-departure-operations",
            kwargs={"slug": self.space.slug, "departure_id": self.departure.pk},
        )
        self.web_url = reverse(
            "organizations:space-work-g3-departure-operations",
            kwargs={"slug": self.space.slug, "departure_id": self.departure.pk},
        )

    def test_work_owner_and_web_handoff_gate_on_operations_manage(self):
        work = self.client.get(reverse(
            "organizations_api:workspace-work",
            kwargs={"slug": self.space.slug},
        ), {"kind": "occurrence", "id": str(self.occurrence.pk)})
        self.assertEqual(work.status_code, 200)
        detail = work.json()["selection"]["owner_depth"]
        self.assertEqual(detail["facts"]["departure_id"], str(self.departure.pk))
        self.assertTrue(detail["facts"]["can_manage_operations"])
        web_depth = reverse(
            "organizations:space-work-depth-g3",
            kwargs={
                "slug": self.space.slug, "kind": "occurrence",
                "owner_id": self.occurrence.pk,
            },
        )
        response = self.client.get(web_depth)
        self.assertEqual(response.status_code, 200)
        links = response.context["work_g3"]["actions"]
        operator_link = next(
            item["url"] for item in links
            if item["label"] == "Exploiter ce départ"
        )
        self.assertTrue(operator_link.startswith(self.web_url))
        self.assertEqual(self.client.get(operator_link).status_code, 200)

    def test_departure_api_assigns_real_vehicle_and_distinguishes_capacity(self):
        first = self.client.get(self.api_url)
        self.assertEqual(first.status_code, 200, first.content)
        body = first.json()
        self.assertEqual(body["owner"]["kind"], "transport_departure")
        self.assertEqual(body["owner"]["id"], str(self.departure.pk))
        self.assertTrue(body["actions"]["can_assign_vehicle"])
        self.assertIsNone(body["vehicle"])
        self.assertEqual(body["vehicles"]["items"][0]["id"], str(self.vehicle.pk))
        self.assertIn("basis", body["capacity"])
        changed = self.client.post(
            self.api_url, {"action": "assign_vehicle", "vehicle": str(self.vehicle.pk)},
            content_type="application/json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertTrue(changed.json()["confirmed_by_owner"])
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.vehicle_id, self.vehicle.pk)
        self.assertEqual(changed["Cache-Control"], "private, no-store")

    def test_departure_reschedule_and_cancel_revalidate_live_state(self):
        new_start = timezone.now() + timedelta(days=5)
        changed = self.client.post(
            self.api_url, {
                "action": "reschedule",
                "timezone": "Africa/Lubumbashi",
                "start_at": new_start.isoformat(),
            }, content_type="application/json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.occurrence.refresh_from_db()
        self.assertEqual(
            self.occurrence.start_at.replace(microsecond=0),
            new_start.replace(microsecond=0),
        )
        denied = self.client.post(
            self.api_url, {"action": "cancel", "confirmed": False},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 400, denied.content)
        cancelled = self.client.post(
            self.api_url, {"action": "cancel", "confirmed": True},
            content_type="application/json",
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, OccurrenceStatus.CANCELLED)
        self.assertFalse(cancelled.json()["actions"]["can_cancel"])

    def test_foreign_vehicle_and_invalid_values_never_change_owner(self):
        foreign_space = Organization.objects.create(
            name="Autre Transport", slug="mt5-other-transport",
            created_by=self.outsider, archetype=SpaceArchetype.TRANSPORT_OPERATOR,
        )
        foreign = Vehicle.objects.create(
            space=foreign_space, label="Bus externe", passenger_capacity=30,
        )
        response = self.client.post(
            self.api_url, {"action": "assign_vehicle", "vehicle": str(foreign.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        bad = self.client.post(self.api_url, {
            "action": "reschedule", "timezone": "Not/AZone",
            "start_at": "2026-11-12T09:00",
        }, content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        self.departure.refresh_from_db()
        self.assertIsNone(self.departure.vehicle_id)

    def test_outsider_and_revoked_mandate_are_not_operator_authority(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.api_url).status_code, 404)
        self.assertEqual(self.client.get(self.web_url).status_code, 404)
        scoped = User.objects.create_user(username="mt5-revoked-operator", password="x")
        mandate = grant_activity_role(
            profile=scoped, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        url = self.api_url + f"?responsibility=mandate:{mandate.pk}"
        web = self.web_url + f"?responsibility=mandate:{mandate.pk}"
        self.client.force_login(scoped)
        self.assertEqual(self.client.get(url).status_code, 200)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(web).status_code, 404)

    def test_activity_mandate_does_not_transfer_fleet_authority(self):
        scoped = User.objects.create_user(username="mt5-scoped-operator", password="x")
        mandate = grant_activity_role(
            profile=scoped, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(scoped)
        url = self.api_url + f"?responsibility=mandate:{mandate.pk}"
        current = self.client.get(url)
        self.assertEqual(current.status_code, 200, current.content)
        self.assertFalse(current.json()["actions"]["can_assign_vehicle"])
        self.assertTrue(current.json()["actions"]["can_reschedule"])
        unauthorized = self.client.post(
            url, {"action": "assign_vehicle", "vehicle": str(self.vehicle.pk)},
            content_type="application/json",
        )
        self.assertEqual(unauthorized.status_code, 400)
        self.departure.refresh_from_db()
        self.assertIsNone(self.departure.vehicle_id)
