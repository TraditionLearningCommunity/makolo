from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization

from .automation import run_recognition_cycle
from .contracts import ImpactChannel, RecognitionSliceCandidate, TemporalProfile
from .models import RecognitionEvaluationWindow, RecognitionLedgerEntry, RecognitionSliceReceipt
from .policy import SimulationPolicyV0
from .services import (
    AttributionShare,
    complete_window,
    ensure_cursor,
    get_due_window,
    get_or_create_account,
    process_impact_slice,
    reconstructed_balance,
    spend_points,
)


class RecognitionKernelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.profile = User.objects.create_user(username="recognition-profile", email="recognition@example.com", password="test-pass")
        self.space = Organization.objects.create(name="Recognition Space", slug="recognition-space", created_by=self.profile)
        self.policy = SimulationPolicyV0()
        self.start = timezone.now().replace(microsecond=0)
        self.cursor = ensure_cursor(policy_version=self.policy.version, start_at=self.start)
        self.window = get_due_window(cursor=self.cursor, now=self.start + timedelta(hours=24))
        self.assertIsNotNone(self.window)

    def test_account_subject_is_exactly_profile_or_space(self):
        profile_account = get_or_create_account(profile=self.profile)
        space_account = get_or_create_account(space=self.space)
        self.assertEqual(profile_account.subject_type, "profile")
        self.assertEqual(space_account.subject_type, "space")
        with self.assertRaises(ValidationError):
            get_or_create_account(profile=self.profile, space=self.space)

    def test_same_slice_is_consumed_once_and_window_pool_is_conserved(self):
        shares = (
            AttributionShare(profile=self.profile, share=Decimal("0.60")),
            AttributionShare(space=self.space, share=Decimal("0.25")),
        )
        result = process_impact_slice(
            window=self.window,
            slice_key="concert:vip-sales:2026-09-07",
            accrual_key="concert:vip-sales:economic",
            channel=ImpactChannel.ECONOMIC.value,
            temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=self.start + timedelta(hours=4),
            available_at=self.start + timedelta(hours=4),
            impact_delta=Decimal("30"),
            attribution_shares=shares,
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        first_pool = result.receipt.pool_points
        self.assertGreater(first_pool, 0)
        self.assertEqual(result.receipt.pool_points, result.receipt.issued_points + result.receipt.unattributed_points)
        before = RecognitionLedgerEntry.objects.count()

        replay = process_impact_slice(
            window=self.window,
            slice_key="concert:vip-sales:2026-09-07",
            accrual_key="concert:vip-sales:economic",
            channel=ImpactChannel.ECONOMIC.value,
            temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=self.start + timedelta(hours=4),
            available_at=self.start + timedelta(hours=4),
            impact_delta=Decimal("30"),
            attribution_shares=shares,
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        self.assertFalse(replay.created)
        self.assertEqual(RecognitionLedgerEntry.objects.count(), before)
        self.assertEqual(RecognitionSliceReceipt.objects.filter(slice_key="concert:vip-sales:2026-09-07").count(), 1)

        self.window.refresh_from_db()
        self.assertEqual(self.window.pool_points, self.window.issued_points + self.window.unattributed_points)
        self.assertEqual(self.window.processed_slices, 1)

    def test_small_persistent_utility_accumulates_until_it_matures_one_point(self):
        shares = (AttributionShare(space=self.space, share=Decimal("1.00")),)
        pools = []
        for day in range(1, 6):
            result = process_impact_slice(
                window=self.window,
                slice_key=f"scholarship:flow:{day}",
                accrual_key="scholarship:2027:real-action",
                channel=ImpactChannel.REAL_ACTION.value,
                temporal_profile=TemporalProfile.FLOW.value,
                occurred_at=self.start + timedelta(hours=day),
                available_at=self.start + timedelta(hours=day),
                impact_delta=Decimal("0.001"),
                attribution_shares=shares,
                points_target_for_cumulative=self.policy.target_points,
                policy_version=self.policy.version,
            )
            pools.append(result.receipt.pool_points)
        self.assertIn(0, pools)
        self.assertGreater(sum(pools), 0)
        account = get_or_create_account(space=self.space)
        self.assertEqual(account.points_balance, sum(pools))

    def test_spending_decrements_balance_without_erasing_lifetime_earned(self):
        share = (AttributionShare(profile=self.profile, share=Decimal("1.00")),)
        process_impact_slice(
            window=self.window,
            slice_key="service:fulfilled:1",
            accrual_key="service:fulfilled:real-action",
            channel=ImpactChannel.REAL_ACTION.value,
            temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=self.start + timedelta(hours=1),
            available_at=self.start + timedelta(hours=1),
            impact_delta=Decimal("10"),
            attribution_shares=share,
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        account = get_or_create_account(profile=self.profile)
        account.refresh_from_db()
        earned_before = account.lifetime_earned
        self.assertGreater(earned_before, 100)

        spend_points(
            account=account,
            points=100,
            idempotency_key="reward:redemption:test-1",
            description="Reward test",
            actor_profile=self.profile,
        )
        account.refresh_from_db()
        self.assertEqual(account.lifetime_earned, earned_before)
        self.assertEqual(account.lifetime_spent, 100)
        self.assertEqual(account.points_balance, earned_before - 100)
        self.assertEqual(reconstructed_balance(account), account.points_balance)

        replay = spend_points(
            account=account,
            points=100,
            idempotency_key="reward:redemption:test-1",
            description="Reward test",
            actor_profile=self.profile,
        )
        self.assertEqual(replay.points, -100)
        account.refresh_from_db()
        self.assertEqual(account.lifetime_spent, 100)

    def test_insufficient_balance_cannot_be_spent(self):
        account = get_or_create_account(profile=self.profile)
        with self.assertRaises(ValidationError):
            spend_points(
                account=account,
                points=1,
                idempotency_key="reward:redemption:insufficient",
                description="Impossible",
                actor_profile=self.profile,
            )

    def test_late_fact_uses_available_at_without_recounting_old_event_time(self):
        result = process_impact_slice(
            window=self.window,
            slice_key="late:scholarship:outcome:1",
            accrual_key="scholarship:2027:real-action",
            channel=ImpactChannel.REAL_ACTION.value,
            temporal_profile=TemporalProfile.FLOW.value,
            occurred_at=self.start - timedelta(days=3),
            available_at=self.start + timedelta(hours=6),
            impact_delta=Decimal("1"),
            attribution_shares=(AttributionShare(space=self.space, share=Decimal("1.00")),),
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        self.assertTrue(result.created)
        self.assertEqual(result.receipt.occurred_at, self.start - timedelta(days=3))
        self.assertEqual(result.receipt.available_at, self.start + timedelta(hours=6))

    def test_slice_available_at_must_belong_to_evaluation_window(self):
        with self.assertRaises(ValidationError):
            process_impact_slice(
                window=self.window,
                slice_key="future:slice",
                accrual_key="future:real-action",
                channel=ImpactChannel.REAL_ACTION.value,
                temporal_profile=TemporalProfile.FLOW.value,
                occurred_at=self.start + timedelta(hours=2),
                available_at=self.start + timedelta(hours=24),
                impact_delta=Decimal("1"),
                attribution_shares=(AttributionShare(profile=self.profile, share=Decimal("1.00")),),
                points_target_for_cumulative=self.policy.target_points,
                policy_version=self.policy.version,
            )

    def test_scheduler_frequency_does_not_change_points_or_reconsume_window(self):
        cursor_key = "recognition-cycle-test"
        ensure_cursor(
            key=cursor_key,
            policy_version=self.policy.version,
            start_at=self.start,
        )
        candidate = RecognitionSliceCandidate(
            slice_key="cycle:late-safe:1",
            accrual_key="cycle:real-action",
            channel=ImpactChannel.REAL_ACTION,
            temporal_profile=TemporalProfile.FLOW,
            occurred_at=self.start - timedelta(days=1),
            available_at=self.start + timedelta(hours=6),
            impact_delta=Decimal("1"),
            attribution_shares=(AttributionShare(profile=self.profile, share=Decimal("1.00")),),
        )

        def provider(starts_at, ends_at):
            self.assertEqual(starts_at, self.start)
            self.assertEqual(ends_at, self.start + timedelta(hours=24))
            return [candidate]

        first = run_recognition_cycle(
            slice_provider=provider,
            policy=self.policy,
            now=self.start + timedelta(hours=24),
            cursor_key=cursor_key,
        )
        self.assertTrue(first["due"])
        account = get_or_create_account(profile=self.profile)
        account.refresh_from_db()
        first_balance = account.points_balance
        self.assertGreater(first_balance, 0)

        replay = run_recognition_cycle(
            slice_provider=lambda _start, _end: [candidate],
            policy=self.policy,
            now=self.start + timedelta(hours=24),
            cursor_key=cursor_key,
        )
        self.assertFalse(replay["due"])
        account.refresh_from_db()
        self.assertEqual(account.points_balance, first_balance)

    def test_ledger_history_rejects_bulk_mutation(self):
        process_impact_slice(
            window=self.window,
            slice_key="immutable:grant",
            accrual_key="immutable:real-action",
            channel=ImpactChannel.REAL_ACTION.value,
            temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=self.start + timedelta(hours=2),
            available_at=self.start + timedelta(hours=2),
            impact_delta=Decimal("2"),
            attribution_shares=(AttributionShare(profile=self.profile, share=Decimal("1.00")),),
            points_target_for_cumulative=self.policy.target_points,
            policy_version=self.policy.version,
        )
        with self.assertRaises(ValidationError):
            RecognitionLedgerEntry.objects.update(description="mutated")

    def test_24h_window_only_advances_after_completion(self):
        self.assertIsNone(get_due_window(cursor=self.cursor, now=self.start + timedelta(hours=23, minutes=59)))
        window = get_due_window(cursor=self.cursor, now=self.start + timedelta(hours=24))
        complete_window(window=window, cursor=self.cursor)
        self.cursor.refresh_from_db()
        self.assertEqual(self.cursor.last_completed_end, self.start + timedelta(hours=24))
        self.assertIsNone(get_due_window(cursor=self.cursor, now=self.start + timedelta(hours=47)))
        self.assertIsNotNone(get_due_window(cursor=self.cursor, now=self.start + timedelta(hours=48)))
