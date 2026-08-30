from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from requirements.contracts import RequirementAssessmentState, RequirementMode

from .contracts import (
    CatalogVisibility,
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
    SubscriptionTransitionError,
    cancel_subscription_transition,
    complete_subscription_transition,
    record_transition_requirement_decision,
    reject_subscription_transition,
    request_subscription_transition,
)


User = get_user_model()


class S4TransitionValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = User.objects.create_user(
            username="s4-validation-profile",
            email="s4-validation-profile@example.test",
            password="x",
        )
        cls.actor = User.objects.create_user(
            username="s4-validation-actor",
            email="s4-validation-actor@example.test",
            password="x",
        )

    def setUp(self):
        self.subscription = Subscription.objects.get(profile=self.profile)

    def version(
        self,
        code,
        *,
        subject_type=SubscriptionSubjectType.PROFILE,
        plan_type=SubscriptionPlanType.ADDON,
        publish=True,
    ):
        plan = SubscriptionPlan.objects.create(
            code=code,
            subject_type=subject_type,
            plan_type=plan_type,
        )
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name=code,
            catalog_visibility=CatalogVisibility.PUBLIC,
        )
        if publish:
            publish_plan_version(version)
            version.refresh_from_db()
        return version

    def requirement(
        self,
        version,
        *,
        key,
        mode,
        evaluator_key="",
        config=None,
        mandatory=True,
        failure_policy=RequirementFailurePolicy.BLOCK,
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
            failure_policy=failure_policy,
        )

    def request(self, version, *, key, expires_at=None):
        return request_subscription_transition(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=version,
            requested_by=self.profile,
            idempotency_key=key,
            expires_at=expires_at,
        )

    def test_draft_target_is_refused(self):
        target = self.version("s4.validation.draft", publish=False)
        with self.assertRaises(SubscriptionTransitionError):
            self.request(target, key="draft")

    def test_subject_mismatch_is_refused(self):
        target = self.version(
            "s4.validation.space",
            subject_type=SubscriptionSubjectType.SPACE,
        )
        with self.assertRaises(SubscriptionTransitionError):
            self.request(target, key="subject-mismatch")

    def test_inactive_plan_is_refused(self):
        target = self.version("s4.validation.inactive")
        target.plan.is_active = False
        target.plan.save(update_fields=["is_active", "updated_at"])
        target.refresh_from_db()
        with self.assertRaises(SubscriptionTransitionError):
            self.request(target, key="inactive")

    def test_automatic_requirement_is_evaluated_on_request(self):
        target = self.version("s4.validation.automatic", publish=False)
        self.requirement(
            target,
            key="account.age",
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 0},
        )
        publish_plan_version(target)

        transition = self.request(target, key="automatic")
        assessment = transition.assessments.get()

        self.assertEqual(assessment.state, RequirementAssessmentState.SATISFIED)
        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)
        self.assertIsNone(assessment.assessed_by_id)

    def test_non_automatic_modes_never_get_fake_success(self):
        target = self.version("s4.validation.manual-modes", publish=False)
        modes = (
            RequirementMode.ACTION,
            RequirementMode.REVIEW,
            RequirementMode.VERIFICATION,
            RequirementMode.EXTERNAL_CHECK,
            RequirementMode.PAYMENT,
        )
        for position, mode in enumerate(modes):
            PlanRequirement.objects.create(
                plan_version=target,
                key=f"manual.{mode}",
                title=f"manual.{mode}",
                phase=RequirementPhase.ACQUISITION,
                mode=mode,
                is_mandatory=True,
                failure_policy=RequirementFailurePolicy.BLOCK,
                position=position,
            )
        publish_plan_version(target)

        transition = self.request(target, key="manual-modes")
        states = set(transition.assessments.values_list("state", flat=True))

        self.assertEqual(states, {RequirementAssessmentState.PENDING})
        self.assertEqual(transition.status, SubscriptionTransitionStatus.IN_PROGRESS)

    def test_not_applicable_mandatory_requirement_is_non_blocking(self):
        target = self.version("s4.validation.not-applicable", publish=False)
        self.requirement(
            target,
            key="action.optional-by-context",
            mode=RequirementMode.ACTION,
        )
        publish_plan_version(target)
        transition = self.request(target, key="not-applicable")
        assessment = transition.assessments.get()

        transition = record_transition_requirement_decision(
            assessment=assessment,
            state=RequirementAssessmentState.NOT_APPLICABLE,
            actor=self.actor,
            reason_code="test.not_applicable",
        )

        self.assertEqual(transition.status, SubscriptionTransitionStatus.READY)

    def test_cancel_reject_and_expire_are_terminal_workflow_outcomes(self):
        cancel_target = self.version("s4.validation.cancel", publish=False)
        self.requirement(cancel_target, key="cancel.action", mode=RequirementMode.ACTION)
        publish_plan_version(cancel_target)
        cancelled = self.request(cancel_target, key="cancel")
        cancelled = cancel_subscription_transition(
            transition=cancelled,
            actor=self.profile,
            reason="user cancelled",
        )
        self.assertEqual(cancelled.status, SubscriptionTransitionStatus.CANCELLED)
        with self.assertRaises(SubscriptionTransitionError):
            complete_subscription_transition(transition=cancelled)

        reject_target = self.version("s4.validation.reject", publish=False)
        self.requirement(reject_target, key="reject.review", mode=RequirementMode.REVIEW)
        publish_plan_version(reject_target)
        rejected = self.request(reject_target, key="reject")
        rejected = reject_subscription_transition(
            transition=rejected,
            actor=self.actor,
            reason="review denied",
        )
        self.assertEqual(rejected.status, SubscriptionTransitionStatus.REJECTED)

        expire_target = self.version("s4.validation.expire", publish=False)
        self.requirement(expire_target, key="expire.action", mode=RequirementMode.ACTION)
        publish_plan_version(expire_target)
        expired = self.request(
            expire_target,
            key="expire",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(expired.status, SubscriptionTransitionStatus.EXPIRED)
