from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from access.models import Access
from activities.models import Activity
from organizations.models import Organization
from promotions.models import DiscountType, Promotion, PromotionCode
from social.models import ActionNeed

from .contracts import ImpactChannel, RecognitionSignalFact, TemporalProfile
from .economy import redeem_reward
from .engine import RuleSpec, evaluate_rule_group
from .ingest import record_signal
from .models import RecognitionObjectEvaluation, RecognitionPolicy, RecognitionRule, RewardDefinition, RewardKind
from .runtime import _temporal_delta, process_signal_group
from .services import AttributionShare, ensure_cursor, get_due_window, get_or_create_account, process_impact_slice, reconstructed_balance, release_due_pending_grants


class RecognitionKFinalizationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="k-final-user", email="k-final@example.test", password="test-pass-2026")
        self.space = Organization.objects.create(name="K Final Space", created_by=self.user)

    def _rule_spec(self, *, profile="pulse", aggregation="SUM", curve=None, signal_kind="access.used", measure=None):
        return RuleSpec(
            code=f"{profile}-{aggregation.lower()}", signal_kind=signal_kind, channel="real_action",
            temporal_profile=profile, scope={}, conditions={},
            measure=measure or {"op": "field", "name": "count"},
            normalization={"kind": "LINEAR", "factor": 1}, curve=curve or {"kind": "LINEAR", "factor": 1},
            modulators=(), aggregation=aggregation, attribution={"strategy": "unattributed"}, combination="additive",
        )

    def _fact(self, sid, *, occurred_at, available_at=None, count="1", kind="access.used", values=None):
        return RecognitionSignalFact(
            sid, kind, "occurrence", "occ-1", occurred_at, available_at or occurred_at,
            f"outcome:{sid}", values or {"count": count}, (), Decimal("1"),
        )

    def test_curve_is_frequency_invariant_across_scheduler_splits(self):
        now = timezone.now().replace(microsecond=0)
        rule = self._rule_spec(curve={"kind": "SQRT", "factor": 1})
        facts = tuple(self._fact(f"s{i}", occurred_at=now + timedelta(hours=i)) for i in range(4))
        one = evaluate_rule_group(signals=facts, rule=rule, parameters={}, policy_version="p:v1", group_identity="one")
        one_delta, _ = _temporal_delta(rule=rule, evaluated=one, prior_state=None)

        state = None; split_total = Decimal("0")
        for index, fact in enumerate(facts):
            result = evaluate_rule_group(signals=(fact,), rule=rule, parameters={}, policy_version="p:v1", group_identity=f"split-{index}")
            delta, state = _temporal_delta(rule=rule, evaluated=result, prior_state=state)
            split_total += delta
        self.assertEqual(split_total, one_delta)
        self.assertEqual(split_total, Decimal("2"))

    def test_window_uses_occurred_at_semantic_bucket_even_when_facts_arrive_late(self):
        monday = timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
        rule = self._rule_spec(profile="window")
        first = self._fact("window-1", occurred_at=monday, available_at=monday + timedelta(days=2))
        second = self._fact("window-2", occurred_at=monday + timedelta(hours=2), available_at=monday + timedelta(days=3))
        state = None; total = Decimal("0")
        for index, fact in enumerate((first, second)):
            result = evaluate_rule_group(
                signals=(fact,), rule=rule, parameters={}, policy_version="p:v1",
                group_identity=f"late-{index}", semantic_window_hours=24,
            )
            delta, state = _temporal_delta(rule=rule, evaluated=result, prior_state=state)
            total += delta
        self.assertEqual(total, Decimal("2"))
        self.assertEqual(len(state["buckets"]), 1)

    def test_transition_decrease_never_claws_back_but_recovery_is_new_value(self):
        now = timezone.now().replace(microsecond=0)
        rule = self._rule_spec(
            profile="transition", aggregation="LATEST_STATE",
            signal_kind="opportunity.revision.published", measure={"op": "field", "name": "version"},
        )
        state = None; deltas = []
        for index, version in enumerate((5, 3, 4)):
            fact = self._fact(
                f"transition-{index}", occurred_at=now + timedelta(hours=index),
                kind="opportunity.revision.published", values={"version": str(version), "count": "1"},
            )
            result = evaluate_rule_group(signals=(fact,), rule=rule, parameters={}, policy_version="p:v1", group_identity=f"transition-{index}")
            delta, state = _temporal_delta(rule=rule, evaluated=result, prior_state=state)
            deltas.append(delta)
        self.assertEqual(deltas, [Decimal("5"), Decimal("0"), Decimal("1")])

    def test_typed_dsl_rejects_money_plus_count_even_with_currency_pinned(self):
        policy = RecognitionPolicy.objects.create(code="typed-final", version=1, name="Typed final")
        rule = RecognitionRule(
            policy=policy, code="bad-dimensional-add", name="Bad dimensional add",
            signal_kind="payment.succeeded", channel="economic", temporal_profile="pulse",
            conditions={"field": "currency", "op": "eq", "value": "USD"},
            measure={"op": "add", "args": [{"op": "field", "name": "amount"}, {"op": "field", "name": "count"}]},
            aggregation="SUM", outcome_identity={"source": "signal.outcome_identity"},
        )
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_cross_channel_rules_create_one_finite_object_pool_before_attribution(self):
        start = timezone.now().replace(microsecond=0) - timedelta(hours=24)
        policy = RecognitionPolicy.objects.create(
            code="object-pool-final", version=1, name="Object pool final",
            parameters={"credits_per_utility": "10", "credit_curve": {"kind": "SQRT", "factor": 1}},
        )
        for code, kind, channel, value in (
            ("economic", "payment.succeeded", "economic", "5"),
            ("action", "access.used", "real_action", "4"),
        ):
            RecognitionRule.objects.create(
                policy=policy, code=code, name=code, signal_kind=kind, channel=channel,
                temporal_profile="pulse", measure={"op": "const", "value": value},
                aggregation="SUM_DISTINCT_OUTCOME", attribution={"strategy": "signal_contributors"},
                outcome_identity={"source": "signal.outcome_identity"},
            )
        contributor = [{"subject_type": "profile", "subject_id": str(self.user.pk), "causal_mode": "enable", "weight": "1"}]
        payment = record_signal(
            signal_id="pool-payment", signal_kind="payment.succeeded", object_type="occurrence", object_id="occ-pool",
            outcome_identity="pool-payment", occurred_at=start + timedelta(hours=1), available_at=start + timedelta(hours=1),
            values={"count": 1}, contributors=contributor,
        )
        access = record_signal(
            signal_id="pool-access", signal_kind="access.used", object_type="occurrence", object_id="occ-pool",
            outcome_identity="pool-access", occurred_at=start + timedelta(hours=2), available_at=start + timedelta(hours=2),
            values={"count": 1}, contributors=contributor,
        )
        cursor = ensure_cursor(key="object-pool-final", policy_version=policy.version_key, start_at=start)
        window = get_due_window(cursor=cursor, now=start + timedelta(hours=24))
        process_signal_group(signals=(payment, access), window=window, policy=policy)
        window.refresh_from_db()
        self.assertEqual(window.pool_points, 30)
        self.assertEqual(window.issued_points, 30)
        evaluation = RecognitionObjectEvaluation.objects.get(window=window)
        self.assertEqual(evaluation.allocations.count(), 1)
        self.assertEqual(evaluation.allocations.get().points, 30)

    def test_pending_credits_mature_once_into_available_balance(self):
        start = timezone.now().replace(microsecond=0)
        cursor = ensure_cursor(key="pending-final", policy_version="pending:v1", start_at=start)
        window = get_due_window(cursor=cursor, now=start + timedelta(hours=24))
        process_impact_slice(
            window=window, slice_key="pending-final-slice", accrual_key="pending-final-accrual",
            channel=ImpactChannel.REAL_ACTION.value, temporal_profile=TemporalProfile.PULSE.value,
            occurred_at=start + timedelta(hours=1), available_at=start + timedelta(hours=1), impact_delta=Decimal("10"),
            attribution_shares=(AttributionShare(profile=self.user, share=Decimal("1")),),
            points_target_for_cumulative=lambda cumulative: int(cumulative), policy_version="pending:v1", maturation_hours=2,
        )
        account = get_or_create_account(profile=self.user); account.refresh_from_db()
        self.assertEqual((account.points_balance, account.pending_points, account.lifetime_earned), (0, 10, 0))
        self.assertEqual(release_due_pending_grants(now=start + timedelta(hours=2)), 0)
        self.assertEqual(release_due_pending_grants(now=start + timedelta(hours=4)), 10)
        self.assertEqual(release_due_pending_grants(now=start + timedelta(hours=5)), 0)
        account.refresh_from_db()
        self.assertEqual((account.points_balance, account.pending_points, account.lifetime_earned), (10, 0, 10))
        self.assertEqual(reconstructed_balance(account), 10)

    def _fund_account(self, points=100):
        account = get_or_create_account(profile=self.user)
        account.points_balance = points; account.lifetime_earned = points; account.save()
        return account

    def test_payout_reward_is_explicit_finance_handoff_not_fake_fulfillment(self):
        account = self._fund_account()
        reward = RewardDefinition.objects.create(
            code="payout-final", version=1, name="Payout final", kind=RewardKind.PAYOUT, points_cost=10,
            fulfillment={"amount": "5.00", "currency": "USD"},
        )
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="payout-final-1", actor_profile=self.user, beneficiary_profile=self.user)
        self.assertEqual(redemption.status, "requested")
        self.assertEqual(redemption.fulfillment_snapshot["delegated_domain"], "payments")
        self.assertEqual(redemption.fulfillment_snapshot["delegation_state"], "awaiting_finance")
        self.assertNotIn("payout_id", redemption.fulfillment_snapshot)

    def test_promotion_reward_delegates_to_private_single_use_code(self):
        account = self._fund_account()
        promotion = Promotion.objects.create(
            organization=self.space, name="Recognition private promotion",
            discount_type=DiscountType.PERCENT, discount_value=Decimal("10"), created_by=self.user,
        )
        reward = RewardDefinition.objects.create(
            code="promotion-final", version=1, name="Promotion final", kind=RewardKind.PROMOTION, points_cost=10,
            fulfillment={"promotion_id": str(promotion.pk)},
        )
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="promotion-final-1", actor_profile=self.user, beneficiary_profile=self.user)
        self.assertEqual(redemption.status, "fulfilled")
        code = PromotionCode.objects.get(pk=redemption.fulfillment_snapshot["promotion_code_id"])
        self.assertTrue(code.is_private)
        self.assertEqual(code.max_redemptions, 1)

    def test_access_reward_delegates_to_access_without_bypassing_user_model(self):
        account = self._fund_account()
        activity = Activity.objects.create(title="Recognition access activity", created_by=self.user, owner_profile=self.user)
        reward = RewardDefinition.objects.create(
            code="access-final", version=1, name="Access final", kind=RewardKind.ACCESS, points_cost=10,
            fulfillment={"activity_id": str(activity.pk), "create_credential": False},
        )
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="access-final-1", actor_profile=self.user, beneficiary_profile=self.user)
        self.assertEqual(redemption.status, "fulfilled")
        self.assertTrue(Access.objects.filter(pk=redemption.fulfillment_snapshot["access_id"], beneficiary=self.user, activity=activity).exists())

    def test_introduction_reward_delegates_to_private_action_need(self):
        account = self._fund_account()
        reward = RewardDefinition.objects.create(
            code="intro-final", version=1, name="Introduction final", kind=RewardKind.INTRODUCTION, points_cost=10,
            fulfillment={"match_kind": "participate", "title": "Trouver une personne utile"},
        )
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="intro-final-1", actor_profile=self.user, beneficiary_profile=self.user)
        self.assertEqual(redemption.status, "fulfilled")
        need = ActionNeed.objects.get(pk=redemption.fulfillment_snapshot["action_need_id"])
        self.assertEqual(need.owner_profile, self.user)
        self.assertEqual(need.visibility, "private")
