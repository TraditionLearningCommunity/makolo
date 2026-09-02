from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from django.utils import timezone


class TrustedReuseDecisionCode(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    NOT_ACCEPTABLE = "not_acceptable"
    ACCEPTABLE = "acceptable"
    ACCEPTABLE_WITH_CONFIRMATION = "acceptable_with_confirmation"


class TrustedReuseReasonCode(str, Enum):
    NO_POLICY = "reuse.no_policy"
    SOURCE_NOT_ALLOWED = "reuse.source_not_allowed"
    SUBJECT_MISMATCH = "reuse.subject_mismatch"
    KIND_MISMATCH = "reuse.kind_mismatch"
    EXPIRED = "reuse.expired"
    NOT_EXPIRED = "reuse.not_expired"
    FRESHNESS_UNKNOWN = "reuse.freshness_unknown"
    FRESHNESS_WITHIN_WINDOW = "reuse.freshness_within_window"
    TOO_OLD = "reuse.too_old"
    PROOF_REVOKED = "reuse.proof_revoked"
    PROOF_TYPE_MATCH = "reuse.proof_type_match"
    LIBRARY_KIND_MATCH = "reuse.library_kind_match"
    JOURNEY_KIND_MATCH = "reuse.journey_kind_match"
    SENSITIVITY_NOT_ALLOWED = "reuse.sensitivity_not_allowed"
    RESTRICTED_NOT_ALLOWED = "reuse.restricted_not_allowed"
    SENSITIVITY_CONFIRMATION = "reuse.sensitivity_confirmation"
    RESTRICTED_CONFIRMATION = "reuse.restricted_confirmation"
    CURRENT_REQUIREMENT = "reuse.current_requirement"
    HISTORICAL_REQUIREMENT = "reuse.historical_requirement"
    PERMISSION_DENIED = "reuse.permission_denied"
    HUMAN_REVIEW_REQUIRED = "reuse.human_review_required"
    CONFIRMATION_REQUIRED = "reuse.confirmation_required"


@dataclass(frozen=True)
class TrustedReuseDecision:
    requirement_id: str
    assessment_id: str
    candidate_source: str
    candidate_source_id: str
    policy_id: str | None
    policy_key: str | None
    decision: TrustedReuseDecisionCode
    reasons: tuple[TrustedReuseReasonCode, ...]
    freshness: str | None
    sensitivity: str | None
    confirmation_required: bool
    materialization_path: str | None
    observed_at: datetime

    def __post_init__(self):
        object.__setattr__(self, "decision", TrustedReuseDecisionCode(self.decision))
        object.__setattr__(
            self,
            "reasons",
            tuple(TrustedReuseReasonCode(reason) for reason in self.reasons),
        )
        observed_at = self.observed_at or timezone.now()
        if not timezone.is_aware(observed_at):
            raise ValueError("TrustedReuseDecision.observed_at must be timezone-aware.")
        object.__setattr__(self, "observed_at", observed_at)

    @property
    def acceptable(self) -> bool:
        return self.decision in {
            TrustedReuseDecisionCode.ACCEPTABLE,
            TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION,
        }
