from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization
from subscriptions.models import FeatureDefinition
from subscriptions.runtime_models import EntitlementGrant

from .contracts import ImpactChannel, RecognitionSignalFact, TemporalProfile
from .economy import accept_redemption, decline_redemption, redeem_reward
from .engine import RuleSpec, evaluate_rule_group
from .ingest import record_signal
from .models import RecognitionPolicy, RewardDefinition, RewardKind
from .selectors import compact_credits
from .services import apply_correction, ensure_cursor, get_due_window, get_or_create_account, process_impact_slice
from .signal_contracts import sanitize_event_values


class RecognitionCompletionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="recognition-k-owner", email="k-owner@example.test", password="test-pass-2026")
        self.other = User.objects.create_user(username="recognition-k-other", email="k-other@example.test", password="test-pass-2026")
        self.space = Organization.objects.create(name="Recognition K Space", created_by=self.owner)

    def test_signal_contract_drops_private_or_irrelevant_domain_event_fields(self):
        event = SimpleNamespace(
            event_type="payment.succeeded",
            space_id=self.space.pk,
            activity_id=None,
            payload={"payment_id": "p-1", "amount": "100.00", "currency": "USD", "buyer_id": str(self.owner.pk), "beneficiary_id": str(self.other.pk), "private_note": "must-never-enter-recognition"},
        )
        values = sanitize_event_values(event)
        self.assertEqual(values["amount"], "100.00")
        self.assertEqual(values["currency"], "USD")
        self.assertNotIn("buyer_id", values)
        self.assertNotIn("beneficiary_id", values)
        self.assertNotIn("private_note", values)

    def test_record_signal_rejects_fields_outside_safe_contract(self):
        with self.assertRaises(ValidationError):
            record_signal(signal_id="unsafe-1", signal_kind="payment.succeeded", object_type="payment", object_id="p-unsafe", outcome_identity="payment:p-unsafe:succeeded", values={"count": 1, "private_note": "secret"})

    def test_policy_dsl_rejects_unpinned_money_formula(self):
        policy = RecognitionPolicy.objects.create(code="money-test", version=1, name="Money test")
        rule = policy.rules.model(
            policy=policy, code="amount-rule", name="Amount rule", signal_kind="payment.succeeded", channel="economic",
            measure={"op": "field", "name": "amount"}, aggregation="SUM", curve={"kind": "LINEAR", "factor": 1},
        )
        with self.assertRaises(ValidationError): rule.full_clean()
        rule.conditions = {"field": "currency", "op": "eq", "value": "USD"}
        rule.full_clean()

    def test_group_aggregation_is_executed_before_curve(self):
        now = timezone.now()
        rule = RuleSpec(
            code="count-two", signal_kind="access.used", channel="real_action", temporal_profile="pulse",
            scope={}, conditions={}, measure={"op": "field", "name": "count"}, normalization={"kind": "LINEAR", "factor": 1},
            curve={"kind": "LINEAR", "factor": 2}, modulators=(), aggregation="SUM", attribution={"strategy": "unattributed"},
        )
        signals = (
            RecognitionSignalFact("s1", "access.used", "access", "a1", now, now, "o1", {"count": "1"}),
            RecognitionSignalFact("s2", "access.used", "access", "a1", now, now, "o2", {"count": "1"}),
        )
        result = evaluate_rule_group(signals=signals, rule=rule, parameters={}, policy_version="p:v1", group_identity="a1:w1")
        self.assertEqual(result.utility_delta, Decimal("4"))

    def test_internal_correction_never_exposes_negative_balance_and_future_earnings_absorb_it(self):
        account = get_or_create_account(profile=self.owner)
        account.points_balance = 5; account.lifetime_earned = 5; account.save()
        apply_correction(account=account, points_to_remove=10, idempotency_key="correction-k-1", reason="engine bug", actor_profile=self.owner)
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 0); self.assertEqual(account.correction_deficit, 5)
        start = timezone.now().replace(microsecond=0)
        cursor = ensure_cursor(key="k-correction", policy_version="k:v1", start_at=start)
        window = get_due_window(cursor=cursor, now=start + timedelta(hours=24))
        process_impact_slice(window=window, slice_key="k:correction:future-earn", accrual_key="k:correction:accrual", channel=ImpactChannel.REAL_ACTION.value, temporal_profile=TemporalProfile.PULSE.value, occurred_at=start + timedelta(hours=1), available_at=start + timedelta(hours=1), impact_delta=Decimal("7"), attribution_shares=(), points_target_for_cumulative=lambda cumulative: int(cumulative), policy_version="k:v1")
        process_impact_slice(window=window, slice_key="k:correction:future-earn-owner", accrual_key="k:correction:owner-accrual", channel=ImpactChannel.REAL_ACTION.value, temporal_profile=TemporalProfile.PULSE.value, occurred_at=start + timedelta(hours=2), available_at=start + timedelta(hours=2), impact_delta=Decimal("7"), attribution_shares=(__import__("recognition.services", fromlist=["AttributionShare"]).AttributionShare(profile=self.owner, share=Decimal("1")),), points_target_for_cumulative=lambda cumulative: int(cumulative), policy_version="k:v1")
        account.refresh_from_db()
        self.assertEqual(account.correction_deficit, 0); self.assertEqual(account.points_balance, 2)

    def _feature(self):
        return FeatureDefinition.objects.create(code="recognition.k.premium", name="Recognition K Premium", domain="recognition", value_type="boolean", supports_profile=True, supports_space=False, aggregation_strategy="BOOLEAN_OR", enforcement_policy="feature_gate")

    def test_reward_for_other_profile_requires_consent_then_delegates_to_entitlement(self):
        feature = self._feature()
        account = get_or_create_account(profile=self.owner); account.points_balance = 100; account.lifetime_earned = 100; account.save()
        reward = RewardDefinition.objects.create(code="k-premium-gift", version=1, name="Premium cadeau", kind=RewardKind.ENTITLEMENT, points_cost=25, beneficiary_allowed=True, acceptance_required=True, fulfillment={"feature_code": feature.code, "value": True, "duration_days": 30})
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="k-premium-gift-1", actor_profile=self.owner, beneficiary_profile=self.other)
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 75); self.assertEqual(redemption.fulfillment_snapshot["consent_state"], "pending")
        self.assertFalse(EntitlementGrant.objects.filter(profile=self.other, feature=feature).exists())
        with self.assertRaises(ValidationError): accept_redemption(redemption=redemption, beneficiary_profile=self.owner)
        redemption = accept_redemption(redemption=redemption, beneficiary_profile=self.other, actor_profile=self.other)
        self.assertEqual(redemption.status, "fulfilled")
        self.assertTrue(EntitlementGrant.objects.filter(profile=self.other, feature=feature, revoked_at__isnull=True).exists())
        self.assertFalse(get_or_create_account(profile=self.other).points_balance)

    def test_declined_benefit_restores_spent_credits_without_creating_earned_credits(self):
        account = get_or_create_account(profile=self.owner); account.points_balance = 100; account.lifetime_earned = 100; account.save()
        reward = RewardDefinition.objects.create(
            code="k-consent-only", version=1, name="Bénéfice avec consentement", points_cost=20,
            beneficiary_allowed=True, acceptance_required=True, fulfillment={"owner_domain": "external"},
        )
        redemption = redeem_reward(owner_account=account, reward=reward, idempotency_key="k-decline-1", actor_profile=self.owner, beneficiary_profile=self.other)
        decline_redemption(redemption=redemption, beneficiary_profile=self.other, actor_profile=self.other)
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 100); self.assertEqual(account.lifetime_earned, 100); self.assertEqual(account.lifetime_spent, 0)

    def test_credit_compaction_supports_large_standard_prefixes_without_new_unit(self):
        self.assertEqual(compact_credits(2_000), "2k crédits")
        self.assertEqual(compact_credits(63_300_000_000), "63,3G crédits")
        self.assertEqual(compact_credits(4_600_000_000_000_000_000_000_000), "4,6Y crédits")
