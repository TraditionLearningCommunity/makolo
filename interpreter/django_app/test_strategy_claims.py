"""A new strategy must not lease an old strategy's pending work."""
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase

from interpreter.django_app.models import InterpretationRun
from interpreter.django_store import claim_interpretations
from interpreter.django_runtime import run_interpreter_cycle
from interpreter.extraction import DeterministicInterpreter
from interpreter.identifiers import make_interpretation_ref


class StrategyClaimTests(TestCase):
    def test_claim_filters_before_limit_and_preserves_old_pending_history(self):
        material_key = "observer:material:v2:claim-test"
        old = InterpretationRun.objects.create(
            interpretation_ref=make_interpretation_ref(material_key=material_key, strategy_fingerprint="old-strategy"),
            observation_ref="observer:observation:v1:claim-test", material_key=material_key,
            target_key="web_url:v1:" + "a" * 64, strategy_key="deterministic-first",
            strategy_version="1.0", strategy_fingerprint="old-strategy",
        )
        current = InterpretationRun.objects.create(
            interpretation_ref=make_interpretation_ref(material_key=material_key, strategy_fingerprint=DeterministicInterpreter.strategy_fingerprint),
            observation_ref=old.observation_ref, material_key=material_key, target_key=old.target_key,
            strategy_key=DeterministicInterpreter.strategy_key,
            strategy_version=DeterministicInterpreter.strategy_version,
            strategy_fingerprint=DeterministicInterpreter.strategy_fingerprint,
        )
        claims = claim_interpretations(worker_id="act1-test", limit=1, strategy_fingerprint=current.strategy_fingerprint)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].interpretation_ref, current.interpretation_ref)
        old.refresh_from_db()
        self.assertEqual(old.lifecycle, "pending")
        self.assertIsNone(old.claim_token)


class WorkerStrategySelectionTests(SimpleTestCase):
    def test_worker_supplies_exact_fingerprint_to_claim_boundary(self):
        from intelligence.registry import IntelligenceRegistry
        with patch("interpreter.django_runtime.build_runtime_registry", return_value=IntelligenceRegistry(providers=[])), \
             patch("interpreter.django_runtime.recover_expired_interpretations", return_value=0), \
             patch("interpreter.django_runtime.enqueue_interpretations", return_value=0), \
             patch("interpreter.django_runtime.claim_interpretations", return_value=()) as claim, \
             patch("interpreter.django_runtime.report_pending_feedback", return_value={"reported": 0, "failed": 0}):
            run_interpreter_cycle(worker_id="act1-test")
        self.assertEqual(claim.call_args.kwargs["strategy_fingerprint"], DeterministicInterpreter.strategy_fingerprint)


class RuntimeStrategyFingerprintTests(SimpleTestCase):
    def test_intelligence_route_changes_strategy_identity(self):
        from intelligence.capabilities import IntelligenceCapability
        from intelligence.providers.base import IntelligenceProvider
        from intelligence.registry import IntelligenceRegistry
        from interpreter.django_runtime import _runtime_strategy

        class ProviderA(IntelligenceProvider):
            key = "route-a"
            capabilities = frozenset({IntelligenceCapability.STRUCTURED_GENERATE})
            model = "model-a"

            def execute(self, request):
                raise AssertionError("fingerprint construction must not call provider")

        class ProviderB(ProviderA):
            key = "route-b"
            model = "model-b"

        with patch(
            "interpreter.django_runtime.build_runtime_registry",
            return_value=IntelligenceRegistry(providers=[ProviderA()]),
        ):
            first = _runtime_strategy()
        with patch(
            "interpreter.django_runtime.build_runtime_registry",
            return_value=IntelligenceRegistry(providers=[ProviderB()]),
        ):
            second = _runtime_strategy()
        self.assertNotEqual(first.strategy_fingerprint, second.strategy_fingerprint)
        self.assertNotEqual(first.strategy_fingerprint, DeterministicInterpreter.strategy_fingerprint)
