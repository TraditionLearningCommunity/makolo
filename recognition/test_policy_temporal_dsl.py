from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from .engine import RuleSpec, evaluate_rule_group
from .contracts import RecognitionSignalFact


class RecognitionTemporalPolicyDslTests(SimpleTestCase):
    def _rule(self, measure):
        return RuleSpec(
            code="temporal-dsl",
            signal_kind="access.used",
            channel="real_action",
            temporal_profile="pulse",
            scope={},
            conditions={},
            measure=measure,
            normalization={"kind": "LINEAR", "factor": 1},
            curve={"kind": "LINEAR", "factor": 1},
            modulators=(),
            aggregation="SUM",
            attribution={"strategy": "unattributed"},
        )

    def _fact(self, occurred_at, available_at):
        return RecognitionSignalFact(
            "time-signal",
            "access.used",
            "occurrence",
            "occ-time",
            occurred_at,
            available_at,
            "time-outcome",
            {"count": "1"},
        )

    def test_hours_between_uses_explicit_signal_times_not_now(self):
        occurred_at = timezone.now().replace(microsecond=0) - timedelta(days=20)
        available_at = occurred_at + timedelta(hours=6)
        rule = self._rule({
            "op": "hours_between",
            "args": [
                {"op": "field", "name": "occurred_at"},
                {"op": "field", "name": "available_at"},
            ],
        })
        result = evaluate_rule_group(
            signals=(self._fact(occurred_at, available_at),),
            rule=rule,
            parameters={},
            policy_version="time:v1",
            group_identity="time:one",
        )
        self.assertEqual(result.utility_delta, Decimal("6"))

    def test_linear_decay_is_deterministic_from_explicit_duration(self):
        occurred_at = timezone.now().replace(microsecond=0) - timedelta(days=100)
        available_at = occurred_at + timedelta(hours=5)
        rule = self._rule({
            "op": "linear_decay",
            "args": [
                {"op": "const", "value": "10"},
                {
                    "op": "hours_between",
                    "args": [
                        {"op": "field", "name": "occurred_at"},
                        {"op": "field", "name": "available_at"},
                    ],
                },
                {"op": "const", "type": "number", "value": "10"},
            ],
        })
        result = evaluate_rule_group(
            signals=(self._fact(occurred_at, available_at),),
            rule=rule,
            parameters={},
            policy_version="time:v1",
            group_identity="time:decay",
        )
        self.assertEqual(result.utility_delta, Decimal("5"))
