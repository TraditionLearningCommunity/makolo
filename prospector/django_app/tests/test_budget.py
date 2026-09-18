from datetime import datetime, timedelta, timezone

from django.test import TestCase

from prospector.django_budget import DjangoBudgetStore
from prospector.django_app.models import (
    ProspectorBudgetCounter,
    ProspectorBudgetReservation,
)
from prospector.errors import ProspectorContractError


class DjangoBudgetStoreTests(TestCase):
    def setUp(self):
        self.store = DjangoBudgetStore()
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.end = self.now + timedelta(hours=1)
        self.kwargs = {
            "policy_key": "test-v1",
            "scopes": {
                "host": "api.example.test",
                "domain": "example.test",
            },
            "limits": {"host": 2, "domain": 3},
            "period_start": self.now,
            "period_end": self.end,
            "now": self.now,
        }

    def test_same_handoff_is_idempotent(self):
        first = self.store.reserve_sync(
            handoff_key="observation:v1:" + ("a" * 64),
            **self.kwargs,
        )
        second = self.store.reserve_sync(
            handoff_key="observation:v1:" + ("a" * 64),
            **self.kwargs,
        )

        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertTrue(second.reused)
        self.assertEqual(ProspectorBudgetReservation.objects.count(), 1)
        self.assertEqual(
            ProspectorBudgetCounter.objects.get(scope_kind="host").used_count,
            1,
        )

    def test_limit_is_atomic_across_multiple_scopes(self):
        for suffix in ("a", "b"):
            decision = self.store.reserve_sync(
                handoff_key="observation:v1:" + (suffix * 64),
                **self.kwargs,
            )
            self.assertTrue(decision.allowed)

        denied = self.store.reserve_sync(
            handoff_key="observation:v1:" + ("c" * 64),
            **self.kwargs,
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.retry_at, self.end)
        self.assertEqual(
            ProspectorBudgetCounter.objects.get(scope_kind="host").used_count,
            2,
        )
        self.assertEqual(
            ProspectorBudgetCounter.objects.get(scope_kind="domain").used_count,
            2,
        )

    def test_same_handoff_with_changed_scopes_is_rejected(self):
        key = "observation:v1:" + ("d" * 64)
        self.store.reserve_sync(handoff_key=key, **self.kwargs)
        changed = dict(self.kwargs)
        changed["scopes"] = {
            "host": "other.example.test",
            "domain": "example.test",
        }
        with self.assertRaises(ProspectorContractError):
            self.store.reserve_sync(handoff_key=key, **changed)
