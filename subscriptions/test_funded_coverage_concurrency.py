"""PostgreSQL regression: one financed seat cannot be accepted twice concurrently."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms
from .contracts import SubscriptionPlanType, SubscriptionSubjectType
from .coverage_services import (
    accept_coverage_allocation, create_coverage, invite_coverage_beneficiary,
)
from .models import PlanVersion, SubscriptionPlan
from .services import publish_plan_version


User = get_user_model()


class FundedCoverageConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.payer = User.objects.create_superuser(
            username="fund-concurrency-payer", email="fcp@example.test", password="x",
        )
        self.left = User.objects.create_user(username="fund-concurrency-left", password="x")
        self.right = User.objects.create_user(username="fund-concurrency-right", password="x")
        plan = SubscriptionPlan.objects.create(
            code="funded.concurrency.plan",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(plan=plan, name="One seat", version=1)
        PlanVersionBillingTerms.objects.create(
            plan_version=version, amount="0.00", currency="USD",
            billing_period_unit=BillingPeriodUnit.DAY, billing_period_count=7,
            coverage_enabled=True, coverage_max_quantity=1,
        )
        publish_plan_version(version)
        now = timezone.now()
        self.coverage = create_coverage(
            actor=self.payer, plan_version=version, payer_profile=self.payer,
            purchased_quantity=1, starts_at=now, ends_at=now + timedelta(days=7),
            request_key="fund-concurrent-cover",
        )
        self.left_invite = invite_coverage_beneficiary(
            actor=self.payer, coverage=self.coverage, profile=self.left, request_key="left",
        )
        self.right_invite = invite_coverage_beneficiary(
            actor=self.payer, coverage=self.coverage, profile=self.right, request_key="right",
        )

    def test_two_profiles_competing_for_last_seat(self):
        if connection.vendor != "postgresql":
            self.skipTest("Le contrat select_for_update est testé sur PostgreSQL.")
        barrier = Barrier(2)

        def attempt(profile_id, allocation_id):
            close_old_connections()
            try:
                barrier.wait(timeout=12)
                profile = User.objects.get(pk=profile_id)
                from .coverage_models import SubscriptionCoverageAllocation
                allocation = SubscriptionCoverageAllocation.objects.get(pk=allocation_id)
                try:
                    accept_coverage_allocation(actor=profile, allocation=allocation)
                except ValidationError:
                    return "denied"
                return "ok"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt, self.left.pk, self.left_invite.pk),
                executor.submit(attempt, self.right.pk, self.right_invite.pk),
            ]
            results = [future.result(timeout=25) for future in futures]
        self.assertCountEqual(results, ["ok", "denied"])
