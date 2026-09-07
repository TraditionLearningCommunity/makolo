from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .achievements import grant_due_achievements
from .ingest import record_signal
from .models import AchievementDefinition, RecognitionPolicy, RecognitionRule
from .runtime import process_signal_group
from .services import ensure_cursor, get_due_window, get_or_create_account


class RecognitionAchievementTrajectoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="recognition-achievement-trajectory",
            email="recognition-achievement-trajectory@example.test",
            password="test-pass-2026",
        )

    def test_distinct_channels_are_derived_from_object_pool_explanation(self):
        start = timezone.now().replace(microsecond=0) - timedelta(hours=24)
        policy = RecognitionPolicy.objects.create(
            code="achievement-trajectory",
            version=1,
            name="Achievement trajectory",
            parameters={"credits_per_utility": "1"},
        )
        for code, signal_kind, channel in (
            ("economic-rule", "payment.succeeded", "economic"),
            ("action-rule", "access.used", "real_action"),
        ):
            RecognitionRule.objects.create(
                policy=policy,
                code=code,
                name=code,
                signal_kind=signal_kind,
                channel=channel,
                temporal_profile="pulse",
                measure={"op": "const", "value": "2"},
                aggregation="SUM_DISTINCT_OUTCOME",
                attribution={"strategy": "signal_contributors"},
                outcome_identity={"source": "signal.outcome_identity"},
            )
        contributor = [{
            "subject_type": "profile",
            "subject_id": str(self.user.pk),
            "causal_mode": "enable",
            "weight": "1",
        }]
        signals = (
            record_signal(
                signal_id="achievement-payment",
                signal_kind="payment.succeeded",
                object_type="occurrence",
                object_id="achievement-occurrence",
                outcome_identity="achievement-payment-outcome",
                occurred_at=start + timedelta(hours=1),
                available_at=start + timedelta(hours=1),
                values={"count": 1},
                contributors=contributor,
            ),
            record_signal(
                signal_id="achievement-access",
                signal_kind="access.used",
                object_type="occurrence",
                object_id="achievement-occurrence",
                outcome_identity="achievement-access-outcome",
                occurred_at=start + timedelta(hours=2),
                available_at=start + timedelta(hours=2),
                values={"count": 1},
                contributors=contributor,
            ),
        )
        cursor = ensure_cursor(
            key="achievement-trajectory",
            policy_version=policy.version_key,
            start_at=start,
        )
        window = get_due_window(cursor=cursor, now=start + timedelta(hours=24))
        process_signal_group(signals=signals, window=window, policy=policy)

        achievement = AchievementDefinition.objects.create(
            code="two-useful-channels",
            name="Deux dimensions utiles",
            criteria={"distinct_channels_gte": 2, "distinct_objects_gte": 1},
        )
        account = get_or_create_account(profile=self.user)
        account.refresh_from_db()
        grants = grant_due_achievements(account=account)
        grant = next(item for item in grants if item.achievement_id == achievement.pk)
        self.assertEqual(grant.evidence["trajectory"]["channels"], 2)
        self.assertGreaterEqual(grant.evidence["trajectory"]["rules"], 2)
