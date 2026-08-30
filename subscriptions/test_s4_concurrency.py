from __future__ import annotations

import threading
import unittest

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from .contracts import (
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
)
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription, SubscriptionItem
from .services import publish_plan_version
from .transition_models import SubscriptionTransition
from .transition_services import (
    SubscriptionTransitionError,
    complete_subscription_transition,
    request_subscription_transition,
)


User = get_user_model()


@unittest.skipUnless(connection.vendor == "postgresql", "S4 concurrency invariants require PostgreSQL")
class S4TransitionConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.profile = User.objects.create_user(
            username="s4-concurrent",
            email="s4-concurrent@example.test",
            password="x",
        )
        self.subscription = Subscription.objects.get(profile=self.profile)

    def published_version(self, code, *, plan_type):
        plan = SubscriptionPlan.objects.create(
            code=code,
            plan_type=plan_type,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name=code)
        publish_plan_version(version)
        return version

    def run_two(self, func):
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                value = func()
                result = ("ok", str(getattr(value, "pk", value)))
            except Exception as exc:
                result = ("error", exc)
            finally:
                connections.close_all()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        return outcomes

    def test_concurrent_different_base_switch_requests_leave_one_open_transition(self):
        first = self.published_version("s4.concurrent.base.one", plan_type=SubscriptionPlanType.BASE)
        second = self.published_version("s4.concurrent.base.two", plan_type=SubscriptionPlanType.BASE)
        subscription_id = self.subscription.pk
        profile_id = self.profile.pk

        targets = [first.pk, second.pk]
        target_lock = threading.Lock()

        def request_one():
            with target_lock:
                target_id = targets.pop()
            return request_subscription_transition(
                subscription=Subscription.objects.get(pk=subscription_id),
                kind=SubscriptionTransitionKind.BASE_SWITCH,
                target_plan_version=PlanVersion.objects.get(pk=target_id),
                requested_by=User.objects.get(pk=profile_id),
                idempotency_key=f"base:{target_id}",
            )

        outcomes = self.run_two(request_one)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
        self.assertEqual(sum(isinstance(value, SubscriptionTransitionError) for kind, value in outcomes if kind == "error"), 1)
        self.assertEqual(SubscriptionTransition.objects.filter(subscription=self.subscription, status__in=["requested", "in_progress", "ready"]).count(), 1)

    def test_concurrent_duplicate_idempotency_returns_one_transition(self):
        version = self.published_version("s4.concurrent.addon.idem", plan_type=SubscriptionPlanType.ADDON)
        subscription_id = self.subscription.pk
        profile_id = self.profile.pk
        version_id = version.pk

        def request_same():
            return request_subscription_transition(
                subscription=Subscription.objects.get(pk=subscription_id),
                kind=SubscriptionTransitionKind.ADDON_ADD,
                target_plan_version=PlanVersion.objects.get(pk=version_id),
                requested_by=User.objects.get(pk=profile_id),
                idempotency_key="concurrent-idempotency",
            )

        outcomes = self.run_two(request_same)
        self.assertTrue(all(kind == "ok" for kind, _ in outcomes), outcomes)
        self.assertEqual(len({value for kind, value in outcomes if kind == "ok"}), 1)
        self.assertEqual(SubscriptionTransition.objects.filter(subscription=self.subscription).count(), 1)

    def test_concurrent_completion_is_idempotent_and_keeps_one_base(self):
        target = self.published_version("s4.concurrent.base.complete", plan_type=SubscriptionPlanType.BASE)
        transition = request_subscription_transition(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            target_plan_version=target,
            requested_by=self.profile,
            idempotency_key="concurrent-complete",
        )
        transition_id = transition.pk

        outcomes = self.run_two(
            lambda: complete_subscription_transition(
                transition=SubscriptionTransition.objects.get(pk=transition_id)
            )
        )
        self.assertTrue(all(kind == "ok" for kind, _ in outcomes), outcomes)
        self.assertEqual(
            SubscriptionItem.objects.filter(
                subscription=self.subscription,
                status=SubscriptionItemStatus.ACTIVE,
                item_type=SubscriptionPlanType.BASE,
            ).count(),
            1,
        )
        transition.refresh_from_db()
        self.assertEqual(transition.status, "completed")

    def test_concurrent_addon_completion_creates_one_active_item(self):
        target = self.published_version("s4.concurrent.addon.complete", plan_type=SubscriptionPlanType.ADDON)
        transition = request_subscription_transition(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.ADDON_ADD,
            target_plan_version=target,
            requested_by=self.profile,
            idempotency_key="concurrent-addon-complete",
        )
        transition_id = transition.pk
        outcomes = self.run_two(
            lambda: complete_subscription_transition(
                transition=SubscriptionTransition.objects.get(pk=transition_id)
            )
        )
        self.assertTrue(all(kind == "ok" for kind, _ in outcomes), outcomes)
        self.assertEqual(
            SubscriptionItem.objects.filter(
                subscription=self.subscription,
                plan=target.plan,
                status=SubscriptionItemStatus.ACTIVE,
            ).count(),
            1,
        )
