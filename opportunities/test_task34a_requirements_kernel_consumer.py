from django.test import SimpleTestCase
from django.utils import timezone

from requirements.contracts import RequirementAssessmentState, RequirementEvaluationResult
from requirements.registry import EvaluatorDefinition, EvaluatorParameter, EvaluatorRegistry


class OpportunityCandidate:
    def __init__(self, score):
        self.score = score


class OpportunitiesRequirementsKernelConsumerTests(SimpleTestCase):
    def test_non_services_consumer_can_evaluate_without_services_dependency(self):
        registry = EvaluatorRegistry()

        def evaluator(subject, config):
            satisfied = subject.score >= config["value"]
            return RequirementEvaluationResult(
                state=RequirementAssessmentState.SATISFIED if satisfied else RequirementAssessmentState.UNSATISFIED,
                reason_code="condition_satisfied" if satisfied else "score_too_low",
                actual_value=subject.score,
                expected_value=config["value"],
                observed_at=timezone.now(),
                retryable=not satisfied,
            )

        registry.register(
            EvaluatorDefinition(
                key="opportunity.test_score",
                evaluator=evaluator,
                supported_subject_type=OpportunityCandidate,
                parameter_schema={"value": EvaluatorParameter(int)},
                operators=(">=",),
            )
        )
        result = registry.evaluate(
            "opportunity.test_score",
            subject=OpportunityCandidate(12),
            config={"operator": ">=", "value": 10},
        )
        self.assertEqual(result.state, RequirementAssessmentState.SATISFIED)
