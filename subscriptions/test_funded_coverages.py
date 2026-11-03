from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from groups.models import (
    Group, GroupMembership, GroupMembershipStatus,
    GroupSnapshot, GroupSnapshotMember,
)
from organizations.models import Organization
from payments.models import PaymentObligationStatus
from payments.obligation_services import satisfy_payment_obligation

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms
from .contracts import (
    EntitlementAggregationStrategy, FeatureEnforcementPolicy, FeatureValueType,
    SubscriptionPlanType, SubscriptionSubjectType,
)
from .coverage_models import AllocationStatus, CoverageStatus, GroupCoveragePolicy, coverage_period_end
from .coverage_services import (
    accept_coverage_allocation, change_coverage_status, create_coverage,
    decide_coverage_allocation, invite_coverage_beneficiary, use_personal_base,
)
from .entitlements import resolve_entitlement
from .models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from .runtime_models import SubscriptionItem
from .services import publish_plan_version


User = get_user_model()


class FinancedCoverageTests(TestCase):
    def setUp(self):
        self.payer = User.objects.create_user(username="fund-payer", password="x")
        self.payer.is_superuser = True
        self.payer.save(update_fields=["is_superuser"])
        self.alice = User.objects.create_user(username="fund-alice", password="x")
        self.bob = User.objects.create_user(username="fund-bob", password="x")
        self.outsider = User.objects.create_user(username="fund-outsider", password="x")
        self.now = timezone.now()
        self.start = self.now - timedelta(minutes=1)
        self.end = coverage_period_end(self.start, "month", 1)

    def offer(self, code="case", *, plan_type=SubscriptionPlanType.ADDON,
              subject_type=SubscriptionSubjectType.PROFILE,
              amount="0.00", quantity=2, pricing="flat"):
        feature = FeatureDefinition.objects.create(
            code=f"funded.{code}.enabled", name=f"Coverage {code}", domain="test",
            value_type=FeatureValueType.BOOLEAN,
            supports_profile=True, supports_space=True,
            aggregation_strategy=EntitlementAggregationStrategy.BOOLEAN_OR,
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )
        plan = SubscriptionPlan.objects.create(
            code=f"funded.{code}.plan",
            plan_type=plan_type, subject_type=subject_type,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name=code)
        PlanEntitlement.objects.create(plan_version=version, feature=feature, value=True)
        PlanVersionBillingTerms.objects.create(
            plan_version=version,
            amount=Decimal(amount), currency="USD",
            billing_period_unit=BillingPeriodUnit.MONTH,
            billing_period_count=1,
            coverage_enabled=True, coverage_pricing_mode=pricing,
            coverage_max_quantity=quantity,
        )
        publish_plan_version(version)
        version.refresh_from_db()
        return feature, version

    def purchase(self, version, *, key="fund-1", count=2, payer=None):
        return create_coverage(
            actor=payer or self.payer, payer_profile=payer or self.payer,
            plan_version=version, purchased_quantity=count,
            starts_at=self.start, ends_at=self.end, request_key=key,
        )

    def invite(self, coverage, beneficiary, key):
        return invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage,
            profile=beneficiary, request_key=key,
        )

    def test_paid_per_seat_uses_real_payer_and_activates_only_after_settlement(self):
        feature, version = self.offer("paid", amount="8.00", quantity=2, pricing="per_seat")
        coverage = self.purchase(version)
        self.assertEqual(coverage.status, CoverageStatus.PENDING_PAYMENT)
        self.assertEqual(coverage.pk, self.purchase(version).pk)
        link = coverage.billing_obligation_links.get()
        obligation = link.obligation
        self.assertIsNone(link.subscription_id)
        self.assertEqual(obligation.amount, Decimal("16.00"))
        self.assertEqual(obligation.payer_profile_id, self.payer.pk)
        self.assertTrue(obligation.payee_platform)
        invitation = self.invite(coverage, self.alice, "alice")
        with self.assertRaises(ValidationError):
            accept_coverage_allocation(actor=self.alice, allocation=invitation)
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)

        satisfy_payment_obligation(obligation=obligation, source="financed-test")
        coverage.refresh_from_db()
        self.assertEqual(coverage.status, CoverageStatus.ACTIVE)
        before_items = SubscriptionItem.objects.filter(subscription__profile=self.alice).count()
        accepted = accept_coverage_allocation(actor=self.alice, allocation=invitation)
        self.assertEqual(accepted.status, AllocationStatus.ACTIVE)
        self.assertEqual(accepted.pk, accept_coverage_allocation(actor=self.alice, allocation=accepted).pk)
        result = resolve_entitlement(self.alice, feature.code)
        self.assertTrue(result.allowed)
        self.assertEqual([source.source_type for source in result.sources], ["funded_addon"])
        self.assertEqual(SubscriptionItem.objects.filter(subscription__profile=self.alice).count(), before_items)
        self.assertIsNone(resolve_entitlement(self.payer, feature.code).effective_value)
        self.assertEqual(coverage.billing_obligation_links.count(), 1)

    def test_seat_limit_and_funding_authority(self):
        feature, version = self.offer("seats", quantity=1)
        coverage = self.purchase(version, count=1)
        a = self.invite(coverage, self.alice, "a")
        b = self.invite(coverage, self.bob, "b")
        with self.assertRaises(PermissionDenied):
            invite_coverage_beneficiary(
                actor=self.outsider, coverage=coverage,
                profile=self.outsider, request_key="attack",
            )
        with self.assertRaises(PermissionDenied):
            accept_coverage_allocation(actor=self.outsider, allocation=a)
        accept_coverage_allocation(actor=self.alice, allocation=a)
        with self.assertRaises(ValidationError):
            accept_coverage_allocation(actor=self.bob, allocation=b)
        self.assertTrue(resolve_entitlement(self.alice, feature.code).allowed)
        self.assertIsNone(resolve_entitlement(self.bob, feature.code).effective_value)
        decide_coverage_allocation(
            actor=self.payer, allocation=a, reason="Place rendue disponible."
        )
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)
        accept_coverage_allocation(actor=self.bob, allocation=b)
        self.assertTrue(resolve_entitlement(self.bob, feature.code).allowed)

    def test_explicit_financed_base_and_personal_fallback(self):
        feature, version = self.offer(
            "base", plan_type=SubscriptionPlanType.BASE,
            quantity=1,
        )
        coverage = self.purchase(version, count=1)
        invitation = self.invite(coverage, self.alice, "alice")
        original = SubscriptionItem.objects.get(
            subscription__profile=self.alice,
            status="active", item_type="base",
        )
        with self.assertRaises(ValidationError):
            accept_coverage_allocation(actor=self.alice, allocation=invitation)
        selected = accept_coverage_allocation(
            actor=self.alice, allocation=invitation, select_base=True,
        )
        self.assertTrue(selected.selected_base)
        result = resolve_entitlement(self.alice, feature.code)
        self.assertTrue(result.allowed)
        self.assertEqual([source.source_type for source in result.sources], ["funded_base"])
        original.refresh_from_db()
        self.assertEqual(original.status, "active")
        use_personal_base(actor=self.alice, profile=self.alice)
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)
        self.assertEqual(
            SubscriptionItem.objects.filter(
                subscription__profile=self.alice, status="active", item_type="base",
            ).count(), 1,
        )

    def test_dynamic_group_requires_explicit_member_allocation(self):
        feature, version = self.offer("group", quantity=1)
        coverage = self.purchase(version, count=1)
        group = Group.objects.create(
            name="Cercle de recherche", owner_profile=self.payer, created_by=self.payer,
        )
        scope = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage, group=group, request_key="group",
        )
        self.assertEqual(scope.status, AllocationStatus.ACTIVE)
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)
        with self.assertRaises(ValidationError):
            invite_coverage_beneficiary(
                actor=self.payer, coverage=coverage,
                profile=self.alice, group_parent=scope, request_key="alice-fail",
            )
        membership = GroupMembership.objects.create(
            group=group, profile=self.alice, status=GroupMembershipStatus.ACTIVE,
        )
        invitation = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage,
            profile=self.alice, group_parent=scope, request_key="alice",
        )
        accept_coverage_allocation(actor=self.alice, allocation=invitation)
        self.assertTrue(resolve_entitlement(self.alice, feature.code).allowed)
        membership.status = GroupMembershipStatus.LEFT
        membership.save()
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)

    def test_snapshot_population_stays_eligible_after_membership_changes(self):
        feature, version = self.offer("snapshot", quantity=1)
        coverage = self.purchase(version, count=1)
        group = Group.objects.create(
            name="Promotion figée", owner_profile=self.payer, created_by=self.payer,
        )
        snapshot = GroupSnapshot.objects.create(
            group=group, name="Promotion du jour", created_by=self.payer,
            member_count=1,
        )
        GroupSnapshotMember.objects.create(snapshot=snapshot, profile=self.alice)
        scope = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage, group=group, request_key="scope",
            group_snapshot=snapshot, group_policy=GroupCoveragePolicy.SNAPSHOT,
        )
        allocation = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage,
            profile=self.alice, group_parent=scope, request_key="alice",
        )
        accept_coverage_allocation(actor=self.alice, allocation=allocation)
        self.assertTrue(resolve_entitlement(self.alice, feature.code).allowed)
        with self.assertRaises(ValidationError):
            invite_coverage_beneficiary(
                actor=self.payer, coverage=coverage,
                profile=self.bob, group_parent=scope, request_key="bob",
            )

    def test_suspension_of_financed_source_does_not_mutate_personal_subscription(self):
        feature, version = self.offer("suspend", quantity=1)
        coverage = self.purchase(version, count=1)
        allocation = self.invite(coverage, self.alice, "alice")
        accept_coverage_allocation(actor=self.alice, allocation=allocation)
        sub = self.alice.subscriptions.get()
        change_coverage_status(
            actor=self.payer, coverage=coverage,
            status=CoverageStatus.SUSPENDED, reason="Pause contractuelle",
        )
        self.assertIsNone(resolve_entitlement(self.alice, feature.code).effective_value)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "active")
        change_coverage_status(
            actor=self.payer, coverage=coverage,
            status=CoverageStatus.ACTIVE, reason="Reprise validée",
        )
        self.assertTrue(resolve_entitlement(self.alice, feature.code).allowed)

    def test_space_beneficiary_remains_a_space_subject(self):
        feature, version = self.offer(
            "space", subject_type=SubscriptionSubjectType.SPACE,
            quantity=1,
        )
        coverage = self.purchase(version, count=1)
        beneficiary_space = Organization.objects.create(
            name="Espace bénéficiaire", created_by=self.bob,
        )
        allocation = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage,
            space=beneficiary_space, request_key="space",
        )
        with self.assertRaises(PermissionDenied):
            accept_coverage_allocation(actor=self.alice, allocation=allocation)
        accepted = accept_coverage_allocation(actor=self.payer, allocation=allocation)
        self.assertEqual(accepted.status, AllocationStatus.ACTIVE)
        self.assertTrue(resolve_entitlement(beneficiary_space, feature.code).allowed)
        self.assertIsNone(resolve_entitlement(self.bob, feature.code).effective_value)

    def test_space_finances_personal_benefit_without_inheriting_personal_rights(self):
        feature, version = self.offer("spacepayer", quantity=1, amount="5.00")
        payer_space = Organization.objects.create(
            name="Espace financeur", created_by=self.payer,
        )
        from .coverage_services import create_coverage
        coverage = create_coverage(
            actor=self.payer, payer_space=payer_space, plan_version=version,
            purchased_quantity=1, starts_at=self.start, ends_at=self.end,
            request_key="space-finances-profile",
        )
        obligation = coverage.billing_obligation_links.get().obligation
        self.assertEqual(obligation.payer_space_id, payer_space.pk)
        self.assertIsNone(obligation.payer_profile_id)
        satisfy_payment_obligation(obligation=obligation, source="space-financing-test")
        coverage.refresh_from_db()
        self.assertEqual(coverage.status, CoverageStatus.ACTIVE)
        invitation = invite_coverage_beneficiary(
            actor=self.payer, coverage=coverage, profile=self.alice, request_key="space-to-alice",
        )
        accept_coverage_allocation(actor=self.alice, allocation=invitation)
        self.assertTrue(resolve_entitlement(self.alice, feature.code).allowed)
        self.assertIsNone(resolve_entitlement(payer_space, feature.code).effective_value)
        self.assertIsNone(resolve_entitlement(self.payer, feature.code).effective_value)
