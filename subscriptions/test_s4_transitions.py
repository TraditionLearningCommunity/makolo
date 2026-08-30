from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from payments.models import (
    PaymentObligationProcessingMode,
    PaymentObligationReason,
)
from payments.obligation_services import create_payment_obligation, satisfy_payment_obligation
from payments.obligation_transitions import waive_payment_obligation
from payments.testing import make_payment_obligation_journey
from requirements.contracts import RequirementAssessmentState, RequirementMode

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    PlanEligibilityStatus,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
    SubscriptionTransitionRequestOrigin,
    SubscriptionTransitionStatus,
)
from .eligibility import resolve_plan_eligibility
from .eligibility_models import PlanRequirement
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription, SubscriptionItem
from .services import publish_plan_version
from .transition_models import (
    SubscriptionRequirementAssessment,
    SubscriptionRequirementAssessmentEvent,
    SubscriptionTransition,
)
from .transition_preview import preview_subscription_change
from .transition_selectors import get_transition_progress
from .transition_services import (
    SubscriptionTransitionError,
    complete_subscription_transition,
    link_transition_payment_obligation,
    record_transition_requirement_decision,
    request_subscription_transition,
    sync_transition_payment_assessment,
)


User = get_user_model()


class S4TransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = User.objects.create_user(
            username="s4-profile",
            email="s4-profile@example.test",
            password="test-only-password",
        )
        cls.staff = User.objects.create_user(
            username="s4-staff",
            email="s4-staff@example.test",
            password="test-only-password",
            is_staff=True,
        )

    def setUp(self):
        self.subscription = Subscription.objects.get(profile=self.profile)

    def make_version(
        self,
        code,
        *,
        plan_type=SubscriptionPlanType.ADDON,
        acquisition=AcquisitionMode.SELF_SERVICE,
    ):
        plan = SubscriptionPlan.objects.create(
            code=code,
            plan_type=plan_type,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        return PlanVersion.objects.create(
            plan=plan,
            version=1,
            name=code,
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=acquisition,
        )

    def add_requirement(
        self,
        version,
        *,
        key,
        mode,
        mandatory=True,
        policy=RequirementFailurePolicy.BLOCK,
        evaluator_key="",
        config=None,
    ):
        return PlanRequirement.objects.create(
            plan_version=version,
            key=key,
            title=key,
            phase=RequirementPhase.ACQUISITION,
            mode=mode,
            evaluator_key=evaluator_key,
            config=config or {},
            is_mandatory=mandatory,
            failure_policy=policy,
        )

    def request(
        self,
        version,
        *,
        kind=SubscriptionTransitionKind.ADDON_ADD,
        key="s4-request",
        source_item=None,
        origin=SubscriptionTransitionRequestOrigin.SELF_SERVICE,
    ):
        return request_subscription_transition(
            subscription=self.subscription,
            kind=kind,
            target_plan_version=version,
            source_item=source_item,
            requested_by=self.profile,
            request_origin=origin,
            idempotency_key=key,
        )

    def make_obligation(self, transition, *, suffix, created_by=None):
        journey = make_payment_obligation_journey(
            manager=self.profile,
            beneficiary=self.profile,
            title=f"S4 payment {suffix}",
        )
        return create_payment_obligation(
            journey=journey,
            reason=PaymentObligationReason.OTHER,
            label=f"S4 controlled obligation {suffix}",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            external_payee_name="Controlled payee",
            created_by=created_by or self.profile,
            source_key=f"s4:{transition.pk}:{suffix}",
        )

    def test_available_addon_request_is_ready_and_idempotent(self):
        version = self.make_version("s4.addon.ready")
        publish_plan_version(version)

        first = self.request(version, key="same-intent")
        second = self.request(version, key="same-intent")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.status, SubscriptionTransitionStatus.READY)
        self.assertEqual(
            SubscriptionTransition.objects.filter(subscription=self.subscription).count(),
            1,
        )

    def test_same_idempotency_key_with_incompatible_intent_is_rejected(self):
        first_version = self.make_version("s4.addon.first")
        second_version = self.make_version("s4.addon.second")
        publish_plan_version(first_version)
        publish_plan_version(second_version)
        self.request(first_version, key="collision")
        with self.assertRaises(SubscriptionTransitionError):
            self.request(second_version, key="collision")

    def test_request_retry_after_completion_returns_original_transition(self):
        version = self.make_version("s4.addon.retry-after-complete")
        publish_plan_version(version)
        transition = self.request(version, key="retry-after-complete")
        complete_subscription_transition(transition=transition)

        retried = self.request(version, key="retry-after-complete")

        self.assertEqual(retried.pk, transition.pk)
        self.assertEqual(retried.status, SubscriptionTransitionStatus.COMPLETED)
        self.assertEqual(
            self.subscription.items.filter(
                plan=version.plan,
                status=SubscriptionItemStatus.ACTIVE,
            ).count(),
            1,
        )

    def test_one_open_mutating_transition_per_subscription(self):
        first_version = self.make_version("s4.addon.open.one")
        second_version = self.make_version("s4.addon.open.two")
        self.add_requirement(
            first_version,
            key="action.pending",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(first_version)
        publish_plan_version(second_version)
        transition = self.request(first_version, key="open-one")
        self.assertEqual(transition.status, SubscriptionTransitionStatus.IN_PROGRESS)
        with self.assertRaises(SubscriptionTransitionError):
            self.request(second_version, key="open-two")

    def test_conditionally_available_materializes_only_pinned_target_requirements(self):
        version = self.make_version("s4.addon.action")
        requirement = self.add_requirement(
            version,
            key="action.required",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(version)
        self.assertEqual(
            resolve_plan_eligibility(self.profile, version).status,
            PlanEligibilityStatus.CONDITIONALLY_AVAILABLE,
        )

        transition = self.request(version, key="conditional")
        assessment = SubscriptionRequirementAssessment.objects.get(
            transition=transition
        )
        self.assertEqual(assessment.plan_requirement_id, requirement.pk)
        self.assertEqual(assessment.state, RequirementAssessmentState.PENDING)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.IN_PROGRESS)

        transition = record_transition_requirement_decision(
            assessment=assessment,
            state=RequirementAssessmentState.SATISFIED,
            actor=self.staff,
            reason_code="review.satisfied",
        )
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)
        self.assertEqual(
            SubscriptionRequirementAssessmentEvent.objects.filter(
                assessment=assessment
            ).count(),
            2,
        )

    def test_optional_pending_requirement_does_not_block_readiness(self):
        version = self.make_version("s4.addon.optional")
        self.add_requirement(
            version,
            key="optional.review",
            mode=RequirementMode.REVIEW,
            mandatory=False,
        )
        publish_plan_version(version)
        transition = self.request(version, key="optional")
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)
        progress = get_transition_progress(transition)
        self.assertEqual(progress.total_mandatory, 0)
        self.assertFalse(progress.needs_review)

    def test_not_eligible_and_hidden_self_service_requests_are_refused(self):
        denied = self.make_version("s4.addon.denied")
        self.add_requirement(
            denied,
            key="age.denied",
            mode=RequirementMode.AUTOMATIC,
            policy=RequirementFailurePolicy.DENY,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 99999},
        )
        publish_plan_version(denied)
        with self.assertRaises(SubscriptionTransitionError):
            self.request(denied, key="denied")

        staff_only = self.make_version(
            "s4.addon.staff",
            acquisition=AcquisitionMode.STAFF_ONLY,
        )
        publish_plan_version(staff_only)
        with self.assertRaises(SubscriptionTransitionError):
            self.request(staff_only, key="hidden")
        staff_transition = self.request(
            staff_only,
            key="staff-origin",
            origin=SubscriptionTransitionRequestOrigin.STAFF,
        )
        self.assertEqual(staff_transition.status, SubscriptionTransitionStatus.READY)

    def test_target_and_requirements_remain_pinned_when_new_version_is_published(self):
        version = self.make_version("s4.addon.pinning")
        requirement = self.add_requirement(
            version,
            key="pin.action",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(version)
        transition = self.request(version, key="pinning")

        v2 = PlanVersion.objects.create(
            plan=version.plan,
            version=2,
            name="s4.addon.pinning.v2",
        )
        self.add_requirement(
            v2,
            key="pin.action.v2",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(v2)

        transition.refresh_from_db()
        assessment = transition.assessments.get()
        self.assertEqual(transition.target_plan_version_id, version.pk)
        self.assertEqual(assessment.plan_requirement_id, requirement.pk)
        self.assertEqual(assessment.plan_requirement.plan_version_id, version.pk)

    def test_base_switch_completion_keeps_exactly_one_active_base(self):
        target = self.make_version(
            "s4.base.pro",
            plan_type=SubscriptionPlanType.BASE,
        )
        publish_plan_version(target)
        old_base = self.subscription.items.get(
            status=SubscriptionItemStatus.ACTIVE,
            item_type=SubscriptionPlanType.BASE,
        )

        transition = self.request(
            target,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            key="base-switch",
        )
        self.assertEqual(transition.source_plan_version_id, old_base.plan_version_id)
        complete_subscription_transition(transition=transition)

        old_base.refresh_from_db()
        transition.refresh_from_db()
        active = self.subscription.items.filter(
            status=SubscriptionItemStatus.ACTIVE,
            item_type=SubscriptionPlanType.BASE,
        )
        self.assertEqual(old_base.status, SubscriptionItemStatus.ENDED)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.get().plan_version_id, target.pk)
        self.assertEqual(active.get().created_via_transition_id, transition.pk)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.COMPLETED)
        self.assertEqual(
            complete_subscription_transition(transition=transition).pk,
            transition.pk,
        )

    def test_base_switch_request_retry_after_completion_is_stable(self):
        target = self.make_version(
            "s4.base.retry",
            plan_type=SubscriptionPlanType.BASE,
        )
        publish_plan_version(target)
        transition = self.request(
            target,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            key="base-retry",
        )
        complete_subscription_transition(transition=transition)

        retried = self.request(
            target,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            key="base-retry",
        )
        self.assertEqual(retried.pk, transition.pk)
        self.assertEqual(retried.status, SubscriptionTransitionStatus.COMPLETED)

    def test_addon_add_and_remove_preserve_item_history(self):
        version = self.make_version("s4.addon.history")
        publish_plan_version(version)
        add_transition = self.request(version, key="addon-add")
        complete_subscription_transition(transition=add_transition)
        item = self.subscription.items.get(
            plan=version.plan,
            status=SubscriptionItemStatus.ACTIVE,
        )

        remove_transition = self.request(
            version,
            kind=SubscriptionTransitionKind.ADDON_REMOVE,
            key="addon-remove",
            source_item=item,
        )
        self.assertEqual(remove_transition.status, SubscriptionTransitionStatus.READY)
        complete_subscription_transition(transition=remove_transition)
        item.refresh_from_db()
        self.assertEqual(item.status, SubscriptionItemStatus.ENDED)
        self.assertIsNotNone(item.ends_at)
        self.assertTrue(item.ended_reason.startswith("subscription_transition:"))

    def test_payment_obligation_bridge_pending_then_satisfied(self):
        version = self.make_version("s4.addon.payment")
        self.add_requirement(
            version,
            key="payment.required",
            mode=RequirementMode.PAYMENT,
        )
        publish_plan_version(version)
        transition = self.request(version, key="payment")
        assessment = transition.assessments.get()
        self.assertEqual(assessment.state, RequirementAssessmentState.PENDING)

        obligation = self.make_obligation(transition, suffix="satisfied")
        link_transition_payment_obligation(
            assessment=assessment,
            obligation=obligation,
            actor=self.profile,
        )
        assessment.refresh_from_db()
        self.assertEqual(assessment.state, RequirementAssessmentState.PENDING)

        satisfy_payment_obligation(obligation=obligation, source="s4-test")
        sync_transition_payment_assessment(obligation=obligation)
        assessment.refresh_from_db()
        transition.refresh_from_db()
        self.assertEqual(assessment.state, RequirementAssessmentState.SATISFIED)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)

    def test_waived_payment_obligation_satisfies_assessment(self):
        version = self.make_version("s4.addon.payment.waived")
        self.add_requirement(
            version,
            key="payment.waived",
            mode=RequirementMode.PAYMENT,
        )
        publish_plan_version(version)
        transition = self.request(version, key="payment-waived")
        assessment = transition.assessments.get()
        obligation = self.make_obligation(
            transition,
            suffix="waived",
            created_by=self.staff,
        )

        link_transition_payment_obligation(
            assessment=assessment,
            obligation=obligation,
            actor=self.staff,
        )
        waive_payment_obligation(obligation=obligation, actor=self.staff)
        sync_transition_payment_assessment(obligation=obligation, actor=self.staff)
        assessment.refresh_from_db()
        self.assertEqual(assessment.state, RequirementAssessmentState.SATISFIED)

    def test_preview_is_read_only(self):
        version = self.make_version("s4.addon.preview")
        self.add_requirement(
            version,
            key="preview.action",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(version)
        before = (
            SubscriptionTransition.objects.count(),
            SubscriptionRequirementAssessment.objects.count(),
            SubscriptionItem.objects.count(),
        )
        first = preview_subscription_change(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=version,
        )
        second = preview_subscription_change(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=version,
        )
        after = (
            SubscriptionTransition.objects.count(),
            SubscriptionRequirementAssessment.objects.count(),
            SubscriptionItem.objects.count(),
        )
        self.assertEqual(before, after)
        self.assertEqual(first, second)
        self.assertEqual(first.requirement_keys, ("preview.action",))
        self.assertEqual(
            first.eligibility.status,
            PlanEligibilityStatus.CONDITIONALLY_AVAILABLE,
        )
