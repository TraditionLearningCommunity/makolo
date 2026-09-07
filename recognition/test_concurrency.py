from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from .contracts import ImpactChannel, TemporalProfile
from .models import RecognitionLedgerEntry
from .policy import SimulationPolicyV0
from .services import (
    AttributionShare,
    ensure_cursor,
    get_due_window,
    get_or_create_account,
    process_impact_slice,
    spend_points,
)


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le verrouillage PostgreSQL réel.")
class RecognitionSpendConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.profile = User.objects.create_user(
            username="recognition-spend-concurrency",
            email="recognition-spend-concurrency@example.com",
            password="Recognition-2026!",
        )
        self.policy = SimulationPolicyV0()
        self.start = timezone.now().replace(microsecond=0)
        cursor = ensure_cursor(
            key="recognition-spend-concurrency",
            policy_version=self.policy.version,
            start_at=self.start,
        )
        window = get_due_window(cursor=cursor, now=self.start + timedelta(hours=24))
        process_impact_slice(
            window=window,
            slice_key="recognition:concurrency:funding",
            accrual_key="recognition:concurrency:funding:real-action",
            channel=ImpactChannel.REAL_ACTION.value,
            temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=self.start + timedelta(hours=1),
            available_at=self.start + timedelta(hours=1),
            impact_delta=Decimal("10"),
            attribution_shares=(AttributionShare(profile=self.profile, share=Decimal("1.00")),),
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        self.account = get_or_create_account(profile=self.profile)
        self.account.refresh_from_db()
        self.initial_balance = self.account.points_balance
        self.assertGreater(self.initial_balance, 0)

    def _spend_entire_balance(self, barrier, suffix):
        close_old_connections()
        try:
            account = type(self.account).objects.get(pk=self.account.pk)
            barrier.wait(timeout=5)
            try:
                spend_points(
                    account=account,
                    points=self.initial_balance,
                    idempotency_key=f"recognition:concurrent-spend:{suffix}",
                    description="Concurrent Recognition spend test",
                    actor_profile=self.profile,
                )
            except ValidationError as exc:
                if "Solde de Points insuffisant" not in str(exc):
                    raise
                return "insufficient"
            return "spent"
        finally:
            connection.close()

    def test_two_simultaneous_spends_cannot_consume_same_balance(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self._spend_entire_balance, barrier, "a"),
                pool.submit(self._spend_entire_balance, barrier, "b"),
            ]
            results = [future.result(timeout=10) for future in futures]

        self.assertEqual(results.count("spent"), 1)
        self.assertEqual(results.count("insufficient"), 1)

        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 0)
        self.assertEqual(self.account.lifetime_spent, self.initial_balance)
        self.assertEqual(
            RecognitionLedgerEntry.objects.filter(account=self.account, kind="spend").count(),
            1,
        )
