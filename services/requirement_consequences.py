from enum import Enum


class ServiceRequirementConsequence(str, Enum):
    ACTION_REQUIRED = "action_required"
    NEEDS_REVIEW = "needs_review"
    PAYMENT_REQUIRED = "payment_required"
    NOT_ELIGIBLE = "not_eligible"
