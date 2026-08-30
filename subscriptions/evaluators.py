from __future__ import annotations

from operator import eq, ge, gt, le, lt

from django.contrib.auth import get_user_model
from django.utils import timezone

from organizations.models import Organization, TeamMembership, TeamMembershipStatus
from requirements.contracts import RequirementAssessmentState, RequirementEvaluationResult
from requirements.registry import EvaluatorDefinition, EvaluatorParameter, RequirementRegistryError, registry


_OPERATORS = {
    ">=": ge,
    ">": gt,
    "==": eq,
    "<=": le,
    "<": lt,
}


def _evaluate_numeric(actual, config, *, reason_prefix):
    expected = config["value"]
    operator = config["operator"]
    satisfied = _OPERATORS[operator](actual, expected)
    return RequirementEvaluationResult(
        state=(RequirementAssessmentState.SATISFIED if satisfied else RequirementAssessmentState.UNSATISFIED),
        reason_code=f"{reason_prefix}.{'satisfied' if satisfied else 'unsatisfied'}",
        actual_value=actual,
        expected_value=expected,
    )


def _profile_account_age_days(subject, config):
    days = max((timezone.now() - subject.created_at).days, 0)
    return _evaluate_numeric(days, config, reason_prefix="profile.account_age_days")


def _space_account_age_days(subject, config):
    days = max((timezone.now() - subject.created_at).days, 0)
    return _evaluate_numeric(days, config, reason_prefix="space.account_age_days")


def _space_member_count(subject, config):
    count = TeamMembership.objects.filter(
        team__organization=subject,
        team__is_active=True,
        status=TeamMembershipStatus.ACTIVE,
    ).values("user_id").distinct().count()
    return _evaluate_numeric(count, config, reason_prefix="space.member_count")


def _non_negative(value):
    return value >= 0


def evaluator_definitions():
    User = get_user_model()
    schema = {"value": EvaluatorParameter(int, validator=_non_negative)}
    operators = tuple(_OPERATORS)
    return (
        EvaluatorDefinition(
            key="profile.account_age_days",
            evaluator=_profile_account_age_days,
            supported_subject_type=User,
            parameter_schema=schema,
            operators=operators,
            dependency_events=(),
            cache_policy="request",
        ),
        EvaluatorDefinition(
            key="space.account_age_days",
            evaluator=_space_account_age_days,
            supported_subject_type=Organization,
            parameter_schema=schema,
            operators=operators,
            dependency_events=(),
            cache_policy="request",
        ),
        EvaluatorDefinition(
            key="space.member_count",
            evaluator=_space_member_count,
            supported_subject_type=Organization,
            parameter_schema=schema,
            operators=operators,
            dependency_events=(),
            cache_policy="request",
        ),
    )


def register_subscription_evaluators():
    for definition in evaluator_definitions():
        try:
            registry.register(definition)
        except RequirementRegistryError as exc:
            if "already registered" not in str(exc):
                raise
