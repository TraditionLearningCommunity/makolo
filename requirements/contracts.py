from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import models
from django.utils import timezone


class RequirementMode(models.TextChoices):
    AUTOMATIC = "automatic", "Automatic"
    ACTION = "action", "Action"
    VERIFICATION = "verification", "Verification"
    EXTERNAL_CHECK = "external_check", "External check"
    PAYMENT = "payment", "Payment"
    REVIEW = "review", "Review"


class RequirementAssessmentState(models.TextChoices):
    UNASSESSED = "unassessed", "Unassessed"
    PENDING = "pending", "Pending"
    SATISFIED = "satisfied", "Satisfied"
    UNSATISFIED = "unsatisfied", "Unsatisfied"
    NOT_APPLICABLE = "not_applicable", "Not applicable"


_REASON_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_ALLOWED_VALUE_TYPES = (str, int, float, bool, Decimal, date, datetime)


def _validate_minimal_value(name: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, _ALLOWED_VALUE_TYPES):
        raise ValueError(f"{name} must be a minimal scalar value.")
    if isinstance(value, str) and len(value) > 500:
        raise ValueError(f"{name} is too large for a RequirementEvaluationResult.")


@dataclass(frozen=True)
class RequirementEvaluationResult:
    state: RequirementAssessmentState
    reason_code: str
    actual_value: Any = None
    expected_value: Any = None
    observed_at: datetime | None = None
    retryable: bool = False

    def __post_init__(self):
        try:
            normalized_state = RequirementAssessmentState(self.state)
        except (TypeError, ValueError) as exc:
            raise ValueError("RequirementEvaluationResult.state is invalid.") from exc
        object.__setattr__(self, "state", normalized_state)

        if not isinstance(self.reason_code, str) or not _REASON_CODE_RE.fullmatch(self.reason_code):
            raise ValueError("reason_code must be a stable lowercase technical code.")
        _validate_minimal_value("actual_value", self.actual_value)
        _validate_minimal_value("expected_value", self.expected_value)

        observed_at = self.observed_at or timezone.now()
        if not isinstance(observed_at, datetime) or not timezone.is_aware(observed_at):
            raise ValueError("observed_at must be a timezone-aware datetime.")
        object.__setattr__(self, "observed_at", observed_at)

        if type(self.retryable) is not bool:
            raise ValueError("retryable must be a boolean.")
