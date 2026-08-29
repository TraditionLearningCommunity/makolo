from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from .contracts import RequirementAssessmentState, RequirementEvaluationResult, RequirementMode
from .registry import (
    EvaluatorDefinition,
    EvaluatorParameter,
    EvaluatorRegistry,
    RequirementConfigurationError,
    RequirementRegistryError,
)


class DummySubject:
    def __init__(self, age_days=120):
        self.age_days = age_days


class OtherSubject:
    pass


def account_age_evaluator(subject, config):
    expected = config["value"]
    operator = config["operator"]
    satisfied = subject.age_days >= expected if operator == ">=" else subject.age_days == expected
    return RequirementEvaluationResult(
        state=RequirementAssessmentState.SATISFIED if satisfied else RequirementAssessmentState.UNSATISFIED,
        reason_code="condition_satisfied" if satisfied else "account_age_too_low",
        actual_value=subject.age_days,
        expected_value=expected,
        observed_at=timezone.now(),
        retryable=not satisfied,
    )


def make_registry():
    registry = EvaluatorRegistry()
    registry.register(
        EvaluatorDefinition(
            key="profile.account_age_days",
            evaluator=account_age_evaluator,
            supported_subject_type=DummySubject,
            parameter_schema={"value": EvaluatorParameter(int, validator=lambda value: value >= 0)},
            operators=(">=", "=="),
            dependency_events=("profile.created",),
            cache_policy="none",
        )
    )
    return registry


class RequirementsContractsTests(SimpleTestCase):
    def test_requirement_mode_values_are_canonical(self):
        self.assertEqual(
            set(RequirementMode.values),
            {"automatic", "action", "verification", "external_check", "payment", "review"},
        )

    def test_assessment_states_are_only_fundamental_truths(self):
        self.assertEqual(
            set(RequirementAssessmentState.values),
            {"unassessed", "pending", "satisfied", "unsatisfied", "not_applicable"},
        )

    def test_evaluation_result_validates_state_observation_and_retryability(self):
        result = RequirementEvaluationResult(
            state="pending",
            reason_code="verification_pending",
            actual_value="submitted",
            expected_value="verified",
            observed_at=timezone.now(),
            retryable=True,
        )
        self.assertEqual(result.state, RequirementAssessmentState.PENDING)
        self.assertTrue(result.retryable)
        self.assertTrue(timezone.is_aware(result.observed_at))

    def test_evaluation_result_rejects_invalid_contract(self):
        with self.assertRaises(ValueError):
            RequirementEvaluationResult(state="action_required", reason_code="invalid", observed_at=timezone.now())
        with self.assertRaises(ValueError):
            RequirementEvaluationResult(state="pending", reason_code="UI message with spaces", observed_at=timezone.now())
        with self.assertRaises(ValueError):
            RequirementEvaluationResult(state="pending", reason_code="pending", observed_at=timezone.now(), retryable=1)


class EvaluatorRegistryTests(SimpleTestCase):
    def test_register_lookup_validate_and_evaluate(self):
        registry = make_registry()
        definition = registry.get("profile.account_age_days")
        self.assertEqual(definition.cache_policy, "none")
        self.assertEqual(definition.dependency_events, ("profile.created",))
        config = registry.validate_config("profile.account_age_days", {"operator": ">=", "value": 90})
        self.assertEqual(config["value"], 90)
        result = registry.evaluate("profile.account_age_days", subject=DummySubject(120), config=config)
        self.assertEqual(result.state, RequirementAssessmentState.SATISFIED)

    def test_duplicate_and_unknown_evaluator_are_rejected(self):
        registry = make_registry()
        with self.assertRaises(RequirementRegistryError):
            registry.register(registry.get("profile.account_age_days"))
        with self.assertRaises(RequirementRegistryError):
            registry.get("subscription.current_plan")

    def test_config_validation_rejects_missing_unknown_wrong_type_and_operator(self):
        registry = make_registry()
        invalid = (
            {"operator": ">="},
            {"operator": ">=", "value": 90, "expression": "__import__('os').system('id')"},
            {"operator": ">=", "value": "90"},
            {"operator": "contains", "value": 90},
            {"operator": ">=", "value": -1},
        )
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(RequirementConfigurationError):
                registry.validate_config("profile.account_age_days", config)

    def test_subject_type_mismatch_is_rejected(self):
        registry = make_registry()
        with self.assertRaises(RequirementConfigurationError):
            registry.evaluate(
                "profile.account_age_days",
                subject=OtherSubject(),
                config={"operator": ">=", "value": 90},
            )

    def test_invalid_evaluator_result_is_rejected(self):
        registry = EvaluatorRegistry()
        registry.register(
            EvaluatorDefinition(
                key="test.invalid",
                evaluator=lambda subject, config: "satisfied",
                supported_subject_type=DummySubject,
            )
        )
        with self.assertRaises(RequirementRegistryError):
            registry.evaluate("test.invalid", subject=DummySubject(), config={})


class RequirementsDependencyBoundaryTests(SimpleTestCase):
    def test_requirements_package_has_no_domain_back_imports(self):
        forbidden = {"services", "subscriptions", "opportunities", "payments", "journeys", "events", "transport"}
        root = Path(__file__).resolve().parent
        violations = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    continue
                overlap = roots & forbidden
                if overlap:
                    violations.append((path.name, sorted(overlap)))
        self.assertEqual(violations, [])
