from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Organization
from payments.models import PaymentObligation, PaymentObligationReason, PaymentObligationStatus
from payments.obligation_services import satisfy_payment_obligation

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms, SubscriptionBillingObligation
from .billing_services import create_subscription_billing_obligation
from .contracts import (
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
    SubscriptionTransitionStatus,
)
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .services import publish_plan_version
from .transition_services import request_subscription_transition


User = get_user_model()


class F2SubscriptionBillingTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="f2-subscription-profile",
            email="f2-subscription-profile@example.test",
            password="x",
        )
        self.space = Organization.objects.create(name="F2 Subscription Space", created_by=self.profile)
        self.profile_subscription = Subscription.objects.get(profile=self.profile)
        self.space_subscription = Subscription.objects.get(space=self.space)

    def plan_with_terms(self, *, code, subject_type, amount):
        plan = SubscriptionPlan.objects.create(
            code=code,
            subject_type=subject_type,
            plan_type=SubscriptionPlanType.ADDON,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name=f"{code} v1")
        terms = PlanVersionBillingTerms.objects.create(
            plan_version=version,
            amount=Decimal(amount),
            currency="usd",
            billing_period_unit=BillingPeriodUnit.MONTH,
            billing_period_count=1,
            payment_due_days=0,
            grace_period_days=3,
        )
        publish_plan_version(version)
        version.refresh_from_db()
        terms.refresh_from_db()
        return version, terms

    def test_free_terms_create_no_positive_obligation(self):
        _, terms = self.plan_with_terms(
            code="f2.free.profile",
            subject_type=SubscriptionSubjectType.PROFILE,
            amount="0.00",
        )
        before = PaymentObligation.objects.count()
        obligation = create_subscription_billing_obligation(
            subscription=self.profile_subscription,
            billing_terms=terms,
            billing_key="free-cycle-1",
            actor=self.profile,
        )
        self.assertIsNone(obligation)
        self.assertEqual(PaymentObligation.objects.count(), before)

    def test_paid_profile_and_space_billing_use_canonical_payer_and_platform_payee(self):
        _, profile_terms = self.plan_with_terms(
            code="f2.paid.profile",
            subject_type=SubscriptionSubjectType.PROFILE,
            amount="11.00",
        )
        _, space_terms = self.plan_with_terms(
            code="f2.paid.space",
            subject_type=SubscriptionSubjectType.SPACE,
            amount="22.00",
        )
        profile_obligation = create_subscription_billing_obligation(
            subscription=self.profile_subscription,
            billing_terms=profile_terms,
            billing_key="profile-cycle-1",
            actor=self.profile,
        )
        space_obligation = create_subscription_billing_obligation(
            subscription=self.space_subscription,
            billing_terms=space_terms,
            billing_key="space-cycle-1",
            actor=self.profile,
        )
        self.assertEqual(profile_obligation.payer_profile_id, self.profile.pk)
        self.assertIsNone(profile_obligation.payer_space_id)
        self.assertEqual(space_obligation.payer_space_id, self.space.pk)
        self.assertIsNone(space_obligation.payer_profile_id)
        for obligation in (profile_obligation, space_obligation):
            self.assertEqual(obligation.reason, PaymentObligationReason.SUBSCRIPTION)
            self.assertTrue(obligation.payee_platform)
            self.assertIsNone(obligation.journey_id)
            self.assertIsNone(obligation.commerce_order_id)
            self.assertIsNone(obligation.step_id)

    def test_paid_transition_is_idempotent_and_financial_readiness_tracks_obligation(self):
        version, terms = self.plan_with_terms(
            code="f2.transition.paid",
            subject_type=SubscriptionSubjectType.PROFILE,
            amount="17.00",
        )
        transition = request_subscription_transition(
            subscription=self.profile_subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=version,
            requested_by=self.profile,
            idempotency_key="f2-paid-transition",
        )
        transition.refresh_from_db()
        self.assertEqual(transition.status, SubscriptionTransitionStatus.IN_PROGRESS)
        link = SubscriptionBillingObligation.objects.get(transition=transition)
        obligation = link.obligation
        self.assertEqual(link.billing_terms_id, terms.pk)
        self.assertEqual(obligation.amount, Decimal("17.00"))
        self.assertIsNone(obligation.journey_id)

        replay = request_subscription_transition(
            subscription=self.profile_subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=version,
            requested_by=self.profile,
            idempotency_key="f2-paid-transition",
        )
        self.assertEqual(replay.pk, transition.pk)
        self.assertEqual(SubscriptionBillingObligation.objects.filter(transition=transition).count(), 1)

        satisfy_payment_obligation(obligation=obligation, source="f2-subscription-test")
        obligation.refresh_from_db()
        transition.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)

    def test_published_billing_terms_are_historical_and_immutable(self):
        _, terms = self.plan_with_terms(
            code="f2.immutable.profile",
            subject_type=SubscriptionSubjectType.PROFILE,
            amount="19.00",
        )
        terms.amount = Decimal("21.00")
        with self.assertRaises(ValidationError):
            terms.save()
        terms.refresh_from_db()
        self.assertEqual(terms.amount, Decimal("19.00"))
