"""PostgreSQL coverage race: no double-spend for one purchased seat."""
from __future__ import annotations

import threading
import unittest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms
from .contracts import SubscriptionPlanType, SubscriptionSubjectType
from .coverage_models import AllocationStatus, coverage_period_end
from .coverage_services import (
    CoverageError, accept_coverage_allocation, create_coverage,
    invite_coverage_beneficiary,
)
from .models import PlanVersion, SubscriptionPlan
from .services import publish_plan_version

User = get_user_model()


@unittest.skipUnless(connection.vendor == "postgresql", "Requires row-level PostgreSQL locks.")
class FinancedSeatConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.payer = User.objects.create_user(username="coverage-race-payer", password="x")
        self.payer.is_superuser = True
        self.payer.save(update_fields=["is_superuser"])
        self.alice = User.objects.create_user(username="coverage-race-alice", password="x")
        self.bob = User.objects.create_user(username="coverage-race-bob", password="x")
        plan = SubscriptionPlan.objects.create(
            code="coverage.race.addon", plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name="Concurrency")
        PlanVersionBillingTerms.objects.create(
            plan_version=version, amount=Decimal("0"),
            currency="USD", billing_period_unit=BillingPeriodUnit.MONTH,
            billing_period_count=1, coverage_enabled=True,
            coverage_pricing_mode="per_seat", coverage_max_quantity=1,
        )
        publish_plan_version(version)
        start = timezone.now() - timedelta(seconds=10)
        pool = create_coverage(
            actor=self.payer, payer_profile=self.payer,
            plan_version=version, purchased_quantity=1,
            starts_at=start, ends_at=coverage_period_end(start, "month", 1),
            request_key="race-purchase-key",
        )
        self.invites = [
            invite_coverage_beneficiary(
                actor=self.payer, coverage=pool, profile=user,
                request_key="race-" + str(user.pk),
            )
            for user in [self.alice, self.bob]
        ]
        self.coverage = pool

    def test_simultaneous_acceptance_never_exceeds_capacity(self):
        barrier = threading.Barrier(2)
        successes = []
        failures = []
        guard = threading.Lock()

        def worker(user_id, allocation_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                from .coverage_models import SubscriptionCoverageAllocation
                allocation = SubscriptionCoverageAllocation.objects.get(pk=allocation_id)
                barrier.wait(timeout=10)
                result = accept_coverage_allocation(actor=user, allocation=allocation)
                with guard:
                    successes.append(result.pk)
            except CoverageError as exc:
                with guard:
                    failures.append(exc)
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=worker, args=(user.pk, allocation.pk))
            for user, allocation in zip([self.alice, self.bob], self.invites)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=25)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1, failures)
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            self.coverage.allocations.filter(
                status=AllocationStatus.ACTIVE, group__isnull=True,
            ).count(), 1,
        )
