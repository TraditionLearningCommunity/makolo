from __future__ import annotations

import secrets

from django.test import TransactionTestCase

from access.models import Access, AccessUse
from accounts.models import User
from activities.models import Activity, Occurrence
from authorization.models import Mandate
from capacity.models import CapacityPool
from commerce.models import CommerceOrder, Offer
from demo_seed.beta import BETA_PERSONAS
from demo_seed.mobile_mature_data import REALITY_SPECS
from demo_seed.mobile_mature_universe import MOBILE_MATURE_PERSONAS, SEED_MARKER
from demo_seed.task22_extension import T22_PERSONAS
from demo_seed.task34b_extension import T34B_PERSONAS
from events.models import Event
from funding.models import FundingDetails
from journeys.models import Journey
from obtention.models import ObtentionDetails
from opportunities.models import OpportunitySource
from preparation.models import ActivityResource
from services.models import ServiceDetails
from notifications.models import Notification
from organizations.models import TeamMembership
from payments.models import Payment
from seed_makolo_demo import run_seed
from transport.models import TransportDeparture, TransportService


class CanonicalBetaSeedTests(TransactionTestCase):
    as_of = "2026-08-21"

    def setUp(self):
        self.password = secrets.token_urlsafe(24)

    def _snapshot(self):
        return {
            "activities": Activity.objects.count(),
            "occurrences": Occurrence.objects.count(),
            "offers": Offer.objects.count(),
            "capacity_pools": CapacityPool.objects.count(),
            "journeys": Journey.objects.count(),
            "orders": CommerceOrder.objects.count(),
            "payments": Payment.objects.count(),
            "accesses": Access.objects.count(),
            "access_uses": AccessUse.objects.count(),
            "departures": TransportDeparture.objects.count(),
            "notifications": Notification.objects.count(),
            "mandates": Mandate.objects.count(),
            "team_memberships": TeamMembership.objects.count(),
            "resources": ActivityResource.objects.count(),
            "mobile_opportunity_sources": OpportunitySource.objects.filter(external_reference__startswith="mobile-mature:").count(),
        }

    def test_beta_seed_requires_explicit_as_of(self):
        with self.assertRaisesRegex(ValueError, "--as-of est obligatoire"):
            run_seed(scale="beta", as_of="", demo_password=self.password)

    def test_beta_seed_is_scenario_valid_and_idempotent(self):
        first = run_seed(scale="beta", as_of=self.as_of, demo_password=self.password)
        first_counts = self._snapshot()
        second = run_seed(scale="beta", as_of=self.as_of, demo_password=self.password)
        second_counts = self._snapshot()

        self.assertEqual(first_counts, second_counts)
        self.assertEqual(first["validation"], second["validation"])
        self.assertEqual(
            set(first["login_examples"]),
            set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values()) | set(T34B_PERSONAS.values()) | set(MOBILE_MATURE_PERSONAS.values()),
        )
        self.assertGreaterEqual(first["validation"]["future_event_occurrences"], 5)
        self.assertGreaterEqual(first["validation"]["future_transport_occurrences"], 5)
        self.assertGreater(first["validation"]["non_event_activities"], 0)
        self.assertGreater(first["validation"]["non_event_access_uses"], 0)
        self.assertEqual(sum(len(rows) for rows in REALITY_SPECS.values()), 150)
        self.assertTrue(all(len(rows) == 25 for rows in REALITY_SPECS.values()))
        seeded = Activity.objects.filter(slug__startswith="mobile-mature-")
        self.assertEqual(seeded.count(), 125)
        self.assertEqual(Event.objects.filter(metadata__seed=SEED_MARKER).count(), 25)
        self.assertEqual(TransportService.objects.filter(activity__in=seeded).count(), 25)
        self.assertEqual(ServiceDetails.objects.filter(activity__in=seeded).count(), 25)
        self.assertEqual(FundingDetails.objects.filter(activity__in=seeded).count(), 25)
        self.assertEqual(ObtentionDetails.objects.filter(activity__in=seeded).count(), 25)
        self.assertEqual(
            OpportunitySource.objects.filter(external_reference__startswith="mobile-mature:").values("opportunity_id").distinct().count(),
            25,
        )
        self.assertGreaterEqual(ActivityResource.objects.filter(activity__in=seeded).count(), 150)
        self.assertGreaterEqual(first["validation"]["mobile_mature_journeys"], 30)
        primary = User.objects.get(email=MOBILE_MATURE_PERSONAS["primary"])
        self.client.force_login(primary)
        now_response = self.client.get("/api/v1/me/now/")
        ongoing_response = self.client.get("/api/v1/me/ongoing/")
        discovery_response = self.client.get("/api/v1/discovery/items/?page_size=50")
        me_response = self.client.get("/api/v1/me/")
        self.assertEqual(now_response.status_code, 200)
        self.assertEqual(ongoing_response.status_code, 200)
        self.assertEqual(discovery_response.status_code, 200)
        self.assertEqual(me_response.status_code, 200)
        self.assertGreater(len(now_response.json()["data"]["items"]), 0)
        self.assertGreater(len(ongoing_response.json()["data"]["items"]), 0)
        discovery_results = discovery_response.json()["data"]["results"]
        self.assertGreaterEqual(len(discovery_results), 20)
        self.assertTrue(
            any(
                any(
                    resource.get("external_url") or resource.get("download_url")
                    for resource in item.get("resources", [])
                )
                for item in discovery_results
            )
        )
        mature_journey = (
            Journey.objects.filter(
                beneficiary=primary,
                activity__slug__startswith="mobile-mature-",
            )
            .order_by("created_at", "id")
            .first()
        )
        self.assertIsNotNone(mature_journey)
        resources_response = self.client.get(
            f"/api/v1/preparation/journeys/{mature_journey.pk}/resources/"
        )
        self.assertEqual(resources_response.status_code, 200)
        resource_rows = resources_response.json()
        self.assertGreaterEqual(len(resource_rows), 2)
        self.assertTrue(
            any(
                row.get("kind") in {"file", "url"}
                and (row.get("download_url") or row.get("external_url"))
                for row in resource_rows
            )
        )
