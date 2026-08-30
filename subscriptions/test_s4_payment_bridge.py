from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from payments.models import (
    Payment,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentProvider,
)
from payments.obligation_services import (
    create_payment_obligation,
    submit_payment_evidence,
    verify_payment_evidence,
)
from payments.services import fail_payment, initiate_obligation_payment
from requirements.contracts import RequirementAssessmentState, RequirementMode
from test_support.payment_obligations import (
    make_payment_obligation_journey,
    make_payment_receipt_artifact,
)

from .contracts import (
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
    SubscriptionTransitionStatus,
)
from .eligibility_models import PlanRequirement
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .services import publish_plan_version
from .transition_services import (
    link_transition_payment_obligation,
    request_subscription_transition,
    sync_transition_payment_assessment,
)


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class S4PaymentBridgeTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="s4-payment-profile",
            email="s4-payment-profile@example.test",
            password="x",
        )
        self.staff = User.objects.create_user(
            username="s4-payment-staff",
            email="s4-payment-staff@example.test",
            password="x",
            is_staff=True,
        )
        self.subscription = Subscription.objects.get(profile=self.profile)
        plan = SubscriptionPlan.objects.create(
            code="s4.payment.bridge",
            subject_type=SubscriptionSubjectType.PROFILE,
            plan_type=SubscriptionPlanType.ADDON,
        )
        self.version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name="S4 payment bridge",
        )
        PlanRequirement.objects.create(
            plan_version=self.version,
            key="payment.required",
            title="Payment required",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.PAYMENT,
            is_mandatory=True,
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        publish_plan_version(self.version)

    def transition(self, key):
        return request_subscription_transition(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=self.version,
            requested_by=self.profile,
            idempotency_key=key,
        )

    def obligation(self, transition, *, mode, key):
        journey = make_payment_obligation_journey(
            manager=self.profile,
            beneficiary=self.profile,
            title=f"S4 payment bridge {key}",
        )
        obligation = create_payment_obligation(
            journey=journey,
            reason=PaymentObligationReason.OTHER,
            label="S4 controlled bridge obligation",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=mode,
            external_payee_name="Controlled payee",
            created_by=self.profile,
            source_key=f"s4-payment:{transition.pk}:{key}",
        )
        return journey, obligation

    def test_failed_payment_attempt_keeps_assessment_pending_when_obligation_is_retryable(self):
        transition = self.transition("provider-failure")
        assessment = transition.assessments.get()
        _, obligation = self.obligation(
            transition,
            mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            key="provider-failure",
        )
        link_transition_payment_obligation(
            assessment=assessment,
            obligation=obligation,
            actor=self.profile,
        )

        payment = initiate_obligation_payment(
            obligation=obligation,
            actor=self.profile,
            provider=PaymentProvider.SANDBOX,
            method="mobile_money",
            idempotency_key="s4-provider-attempt-1",
        )
        fail_payment(payment=payment, failure_code="declined")
        sync_transition_payment_assessment(obligation=obligation)

        obligation.refresh_from_db()
        assessment.refresh_from_db()
        transition.refresh_from_db()
        self.assertEqual(obligation.status, "pending")
        self.assertEqual(assessment.state, RequirementAssessmentState.PENDING)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.IN_PROGRESS)

    def test_verified_external_evidence_satisfies_without_creating_fake_payment(self):
        transition = self.transition("external-evidence")
        assessment = transition.assessments.get()
        journey, obligation = self.obligation(
            transition,
            mode=PaymentObligationProcessingMode.EXTERNAL,
            key="external-evidence",
        )
        link_transition_payment_obligation(
            assessment=assessment,
            obligation=obligation,
            actor=self.profile,
        )
        artifact = make_payment_receipt_artifact(
            journey=journey,
            uploaded_by=self.profile,
            marker=b"s4-external",
        )
        before_payments = Payment.objects.count()

        evidence = submit_payment_evidence(
            obligation=obligation,
            artifact=artifact,
            actor=self.profile,
            paid_at=timezone.now(),
            external_reference="S4-EXT-1",
        )
        sync_transition_payment_assessment(obligation=obligation)
        assessment.refresh_from_db()
        self.assertEqual(assessment.state, RequirementAssessmentState.PENDING)
        self.assertEqual(Payment.objects.count(), before_payments)

        verify_payment_evidence(
            evidence=evidence,
            actor=self.staff,
            review_note="Verified for S4 bridge contract",
        )
        sync_transition_payment_assessment(obligation=obligation, actor=self.staff)

        obligation.refresh_from_db()
        assessment.refresh_from_db()
        transition.refresh_from_db()
        self.assertEqual(obligation.status, "satisfied")
        self.assertEqual(assessment.state, RequirementAssessmentState.SATISFIED)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)
        self.assertEqual(Payment.objects.count(), before_payments)
