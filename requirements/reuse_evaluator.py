from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone

from .models import RequirementReusePolicy, RequirementReuseSource
from .trusted_reuse import TrustedReuseDecision, TrustedReuseDecisionCode, TrustedReuseReasonCode


ACCESS_ALLOWED_TO_PROPOSE = "allowed_to_propose"
FRESHNESS_EXPIRED = "expired"
FRESHNESS_NOT_EXPIRED = "not_expired"
SENSITIVITY_SENSITIVE = "sensitive"
SENSITIVITY_RESTRICTED = "restricted"
PROOF_REVOKED = "revoked"
JOURNEY_TO_LIBRARY_PATH = "journey_artifact_to_personal_asset"


def _enum_value(value):
    return getattr(value, "value", value)


def _observed_date(value: datetime) -> date:
    return timezone.localdate(value) if timezone.is_aware(value) else value.date()


def _decision(*, requirement, assessment_id, candidate, code, reasons, policy=None, observed_at):
    return TrustedReuseDecision(
        requirement_id=str(requirement.pk),
        assessment_id=str(assessment_id) if assessment_id is not None else None,
        candidate_source=_enum_value(candidate.source),
        candidate_source_id=str(candidate.source_id),
        policy_id=str(policy.pk) if policy is not None else None,
        policy_key=policy.key if policy is not None else None,
        decision=code,
        reasons=tuple(reasons),
        freshness=_enum_value(candidate.freshness) if candidate.freshness is not None else None,
        sensitivity=_enum_value(candidate.sensitivity) if candidate.sensitivity is not None else None,
        confirmation_required=(code == TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION),
        materialization_path=_enum_value(candidate.materialization_path) if candidate.materialization_path is not None else None,
        observed_at=observed_at,
    )


def evaluate_trusted_reuse_candidate(
    *,
    requirement,
    candidate,
    expected_subject_type,
    expected_subject_id,
    source_date=None,
    assessment_id=None,
    observed_at=None,
    policies=None,
    current_requirement=True,
):
    """Evaluate Q4 acceptance from explicit candidate facts without mutation.

    The caller owns source authorization and supplies the exact target subject and
    canonical source date. The Requirements domain owns policy matching and never
    infers acceptance from titles, hashes, filenames or fuzzy similarity.
    """

    observed_at = observed_at or timezone.now()
    if not timezone.is_aware(observed_at):
        raise ValueError("Trusted Reuse evaluation requires a timezone-aware observed_at.")

    if not current_requirement:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.NOT_APPLICABLE,
            reasons=(TrustedReuseReasonCode.HISTORICAL_REQUIREMENT,),
            observed_at=observed_at,
        )

    if _enum_value(candidate.access_state) != ACCESS_ALLOWED_TO_PROPOSE:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
            reasons=(TrustedReuseReasonCode.PERMISSION_DENIED,),
            observed_at=observed_at,
        )

    candidate_subject_type = _enum_value(candidate.subject.subject_type)
    if candidate_subject_type != _enum_value(expected_subject_type) or str(candidate.subject.source_id) != str(expected_subject_id):
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
            reasons=(TrustedReuseReasonCode.SUBJECT_MISMATCH,),
            observed_at=observed_at,
        )

    all_policies = list(
        policies
        if policies is not None
        else RequirementReusePolicy.objects.filter(requirement_id=requirement.pk).order_by("key", "id")
    )
    source = _enum_value(candidate.source)
    source_policies = [policy for policy in all_policies if policy.source_type == source]
    if source == RequirementReuseSource.PROOF:
        exact_policies = [policy for policy in source_policies if policy.proof_type == candidate.kind]
    else:
        exact_policies = [policy for policy in source_policies if policy.artifact_kind == candidate.kind]

    if not all_policies:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.UNKNOWN,
            reasons=(TrustedReuseReasonCode.NO_POLICY, TrustedReuseReasonCode.CURRENT_REQUIREMENT),
            observed_at=observed_at,
        )
    if not source_policies:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
            reasons=(TrustedReuseReasonCode.SOURCE_NOT_ALLOWED, TrustedReuseReasonCode.CURRENT_REQUIREMENT),
            observed_at=observed_at,
        )
    if not exact_policies:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
            reasons=(TrustedReuseReasonCode.KIND_MISMATCH, TrustedReuseReasonCode.CURRENT_REQUIREMENT),
            observed_at=observed_at,
        )
    if len(exact_policies) != 1:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            code=TrustedReuseDecisionCode.UNKNOWN,
            reasons=(TrustedReuseReasonCode.POLICY_AMBIGUOUS, TrustedReuseReasonCode.CURRENT_REQUIREMENT),
            observed_at=observed_at,
        )

    policy = exact_policies[0]
    reasons = [TrustedReuseReasonCode.CURRENT_REQUIREMENT]
    if source == RequirementReuseSource.PROOF:
        if candidate.status == PROOF_REVOKED:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
                reasons=(*reasons, TrustedReuseReasonCode.PROOF_REVOKED),
                observed_at=observed_at,
            )
        reasons.append(TrustedReuseReasonCode.PROOF_TYPE_MATCH)
    elif source == RequirementReuseSource.LIBRARY:
        reasons.append(TrustedReuseReasonCode.LIBRARY_KIND_MATCH)
    elif source == RequirementReuseSource.JOURNEY_ARTIFACT:
        if _enum_value(candidate.materialization_path) != JOURNEY_TO_LIBRARY_PATH:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.NOT_APPLICABLE,
                reasons=(*reasons, TrustedReuseReasonCode.PERMISSION_DENIED),
                observed_at=observed_at,
            )
        reasons.append(TrustedReuseReasonCode.JOURNEY_KIND_MATCH)

    freshness = _enum_value(candidate.freshness)
    if freshness == FRESHNESS_EXPIRED:
        return _decision(
            requirement=requirement,
            assessment_id=assessment_id,
            candidate=candidate,
            policy=policy,
            code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
            reasons=(*reasons, TrustedReuseReasonCode.EXPIRED),
            observed_at=observed_at,
        )
    if source != RequirementReuseSource.PROOF:
        if freshness == FRESHNESS_NOT_EXPIRED:
            reasons.append(TrustedReuseReasonCode.NOT_EXPIRED)
        elif policy.require_not_expired:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.UNKNOWN,
                reasons=(*reasons, TrustedReuseReasonCode.FRESHNESS_UNKNOWN),
                observed_at=observed_at,
            )

    if policy.max_age_days is not None:
        if source_date is None:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.UNKNOWN,
                reasons=(*reasons, TrustedReuseReasonCode.FRESHNESS_UNKNOWN),
                observed_at=observed_at,
            )
        if source_date < _observed_date(observed_at) - timedelta(days=policy.max_age_days):
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
                reasons=(*reasons, TrustedReuseReasonCode.TOO_OLD),
                observed_at=observed_at,
            )
        reasons.append(TrustedReuseReasonCode.FRESHNESS_WITHIN_WINDOW)

    confirmation_required = bool(candidate.confirmation_required)
    sensitivity = _enum_value(candidate.sensitivity)
    if sensitivity == SENSITIVITY_RESTRICTED:
        if not policy.allow_restricted_with_confirmation:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
                reasons=(*reasons, TrustedReuseReasonCode.RESTRICTED_NOT_ALLOWED),
                observed_at=observed_at,
            )
        confirmation_required = True
        reasons.extend((TrustedReuseReasonCode.RESTRICTED_CONFIRMATION, TrustedReuseReasonCode.CONFIRMATION_REQUIRED))
    elif sensitivity == SENSITIVITY_SENSITIVE:
        if not policy.allow_sensitive_with_confirmation:
            return _decision(
                requirement=requirement,
                assessment_id=assessment_id,
                candidate=candidate,
                policy=policy,
                code=TrustedReuseDecisionCode.NOT_ACCEPTABLE,
                reasons=(*reasons, TrustedReuseReasonCode.SENSITIVITY_NOT_ALLOWED),
                observed_at=observed_at,
            )
        confirmation_required = True
        reasons.extend((TrustedReuseReasonCode.SENSITIVITY_CONFIRMATION, TrustedReuseReasonCode.CONFIRMATION_REQUIRED))
    elif confirmation_required:
        reasons.append(TrustedReuseReasonCode.CONFIRMATION_REQUIRED)

    if policy.human_review_required:
        reasons.append(TrustedReuseReasonCode.HUMAN_REVIEW_REQUIRED)

    return _decision(
        requirement=requirement,
        assessment_id=assessment_id,
        candidate=candidate,
        policy=policy,
        code=(
            TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION
            if confirmation_required
            else TrustedReuseDecisionCode.ACCEPTABLE
        ),
        reasons=reasons,
        observed_at=observed_at,
    )
