from __future__ import annotations

import threading
import unittest

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from organizations.models import Organization

from .models import Subscription, SubscriptionItem
from .runtime_services import ensure_subscription_for_profile, ensure_subscription_for_space


User = get_user_model()


@unittest.skipUnless(connection.vendor == "postgresql", "S2 concurrency invariants require PostgreSQL")
class SubscriptionConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def _run_concurrently(self, func, subject_pk):
        barrier = threading.Barrier(2)
        errors = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                func(subject_pk)
            except Exception as exc:  # assertions inspect exact absence below
                errors.append(exc)
            finally:
                # Worker threads own separate Django/PostgreSQL connections.
                # Close them explicitly so the test database can be dropped.
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])

    def test_profile_bootstrap_concurrency_keeps_one_subscription_and_base(self):
        profile = User.objects.create_user(username="s2-concurrent-profile", email="s2-concurrent-profile@example.test", password="x")
        Subscription.objects.get(profile=profile).delete()

        def ensure(pk):
            ensure_subscription_for_profile(User.objects.get(pk=pk))

        self._run_concurrently(ensure, profile.pk)
        subscription = Subscription.objects.get(profile=profile)
        self.assertEqual(Subscription.objects.filter(profile=profile).count(), 1)
        self.assertEqual(SubscriptionItem.objects.filter(subscription=subscription, status="active", item_type="base").count(), 1)

    def test_space_bootstrap_concurrency_keeps_one_subscription_and_base(self):
        creator = User.objects.create_user(username="s2-concurrent-owner", email="s2-concurrent-owner@example.test", password="x")
        space = Organization.objects.create(name="S2 Concurrent Space", created_by=creator)
        Subscription.objects.get(space=space).delete()

        def ensure(pk):
            ensure_subscription_for_space(Organization.objects.get(pk=pk))

        self._run_concurrently(ensure, space.pk)
        subscription = Subscription.objects.get(space=space)
        self.assertEqual(Subscription.objects.filter(space=space).count(), 1)
        self.assertEqual(SubscriptionItem.objects.filter(subscription=subscription, status="active", item_type="base").count(), 1)
