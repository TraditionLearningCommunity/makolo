from __future__ import annotations

import secrets

from django.test import TransactionTestCase

from access.models import Access, AccessUse
from activities.models import Activity, Occurrence
from authorization.models import Mandate
from capacity.models import CapacityPool
from commerce.models import CommerceOrder, Offer
from demo_seed.beta import BETA_PERSONAS
from demo_seed.task22_extension import T22_PERSONAS
from journeys.models import Journey
from notifications.models import Notification
from organizations.models import TeamMembership
from payments.models import Payment
from seed_makolo_demo import run_seed
from transport.models import TransportDeparture


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
            set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values()),
        )
        self.assertGreaterEqual(first["validation"]["future_event_occurrences"], 5)
        self.assertGreaterEqual(first["validation"]["future_transport_occurrences"], 5)
        self.assertGreater(first["validation"]["non_event_activities"], 0)
        self.assertGreater(first["validation"]["non_event_access_uses"], 0)
