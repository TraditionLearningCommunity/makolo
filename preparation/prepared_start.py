from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.utils import timezone

from journeys.models import ExternalBeneficiary
from opportunities.models import Opportunity, OpportunityPublicationStatus, OpportunityRequirement, OpportunityRevision
from personal_assets.action_memory import ActionMemorySubjectType
from personal_assets.prepared_memory import PreparedActionMemoryCandidate, prepared_action_memory_for_subject
from readiness.types import NextAction, ReadinessCheck, ReadinessCheckState, ReadinessResult, ReadinessStatus
from requirements.contracts import RequirementAssessmentState
from requirements.models import RequirementReusePolicy
from requirements.reuse_evaluator import evaluate_trusted_reuse_candidate
from requirements.trusted_reuse import TrustedReuseDecision, TrustedReuseDecisionCode, TrustedReuseReasonCode


PREPARED_READY_REASON = "prepared_start.trusted_reuse_ready"
PREPARED_REVIEW_REASON = "prepared_start.human_review_required"
PREPARED_CONFIRM_REASON = "prepared_start.confirmation_required"
PREPARED_UNKNOWN_REASON = "prepared_start.acceptance_unknown"
PREPARED_MISSING_REASON = "prepared_start.no_acceptable_candidate"


class PreparedRequirementState(str, Enum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    CONFIRMATION_REQUIRED = "confirmation_required"
    UNKNOWN = "unknown"
    MISSING = "missing"


@dataclass(frozen=True)
class PreparedStartContext:
    actor_id: str
    viewer_id: str
    controller_id: str
    subject_type: str
    subject_id: str
    beneficiary_type: str
    beneficiary_id: str
    initiator_id: str


@dataclass(frozen=True)
class PreparedReuseOption:
    candidate_source: str
    candidate_source_id: str
    policy_id: str | None
    policy_key: str | None
    decision: TrustedReuseDecisionCode
    reason_codes: tuple[str, ...]
    freshness: str | None
    sensitivity: str | None
    confirmation_required: bool


@dataclass(frozen=True)
class PreparedRequirementResult:
    requirement_id: str
    kind: str
    title: str
    mandatory: bool
    position: int
    assessment_state: RequirementAssessmentState
    preparation_state: PreparedRequirementState
    readiness_check: ReadinessCheck
    reason_codes: tuple[str, ...]
    reuse_options: tuple[PreparedReuseOption, ...]


@dataclass(frozen=True)
class PreparedStartSummary:
    total_requirements: int
    mandatory_requirements: int
    ready_requirements: int
    review_required_requirements: int
    confirmation_required_requirements: int
    unknown_requirements: int
    missing_requirements: int


@dataclass(frozen=True)
class PreparedStartResult:
    context: PreparedStartContext
    opportunity_id: str
    revision_id: str
    revision_version: int
    observed_at: datetime
    readiness: ReadinessResult
    requirements: tuple[PreparedRequirementResult, ...]
    summary: PreparedStartSummary


@dataclass(frozen=True)
class PreparedRevisionRevalidation:
    opportunity_id: str
    observed_revision_id: str
    observed_revision_version: int
    current_revision_id: str | None
    current_revision_version: int | None
    is_current_revision: bool
    has_newer_revision: bool
    opportunity_publication_status: str
    observed_at: datetime


def _identity(value: Any) -> tuple[str, str]:
    User = get_user_model()
    if isinstance(value, User):
        return "profile", str(value.pk)
    if isinstance(value, ExternalBeneficiary):
        return "external_beneficiary", str(value.pk)
    raise ValidationError("Prepared Start exige un Profile ou un ExternalBeneficiary explicite.")


def _authorize_context(*, actor, viewer, subject, controller, beneficiary, initiator):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Prepared Start exige un acteur authentifié.")

    viewer = viewer or actor
    subject = subject or actor
    controller = controller or actor
    beneficiary = beneficiary or subject
    initiator = initiator or actor

    actor_identity = _identity(actor)
    viewer_identity = _identity(viewer)
    subject_identity = _identity(subject)
    controller_identity = _identity(controller)
    beneficiary_identity = _identity(beneficiary)
    initiator_identity = _identity(initiator)

    if viewer_identity != actor_identity:
        raise PermissionDenied("Le viewer Prepared Start doit être l'acteur dans le contrat pré-Journey actuel.")
    if controller_identity != actor_identity or initiator_identity != actor_identity:
        raise PermissionDenied("Prepared Start ne déduit pas une délégation pré-Journey depuis une responsabilité ou un Mandate non spécifique.")
    if beneficiary_identity != subject_identity:
        raise PermissionDenied("Prepared Start ne déduit pas qu'un bénéficiaire distinct autorise l'accès aux faits du sujet.")

    if subject_identity[0] == "profile":
        if subject_identity != actor_identity:
            raise PermissionDenied("Prepared Start n'ouvre pas l'historique d'un autre Profile sans ancre Journey autorisée.")
    elif subject.created_by_id != actor.pk:
        raise PermissionDenied("Cet ExternalBeneficiary n'appartient pas au périmètre contrôlé par cet utilisateur.")

    return subject, PreparedStartContext(
        actor_id=actor_identity[1],
        viewer_id=viewer_identity[1],
        controller_id=controller_identity[1],
        subject_type=subject_identity[0],
        subject_id=subject_identity[1],
        beneficiary_type=beneficiary_identity[0],
        beneficiary_id=beneficiary_identity[1],
        initiator_id=initiator_identity[1],
    )


def _subject_type(context):
    return (
        ActionMemorySubjectType.PROFILE
        if context.subject_type == "profile"
        else ActionMemorySubjectType.EXTERNAL_BENEFICIARY
    )


def _option(decision: TrustedReuseDecision) -> PreparedReuseOption:
    return PreparedReuseOption(
        candidate_source=decision.candidate_source,
        candidate_source_id=decision.candidate_source_id,
        policy_id=decision.policy_id,
        policy_key=decision.policy_key,
        decision=decision.decision,
        reason_codes=tuple(reason.value for reason in decision.reasons),
        freshness=decision.freshness,
        sensitivity=decision.sensitivity,
        confirmation_required=decision.confirmation_required,
    )


def _unique_reason_codes(decisions):
    seen = set()
    result = []
    for decision in decisions:
        for reason in decision.reasons:
            value = reason.value
            if value not in seen:
                seen.add(value)
                result.append(value)
    return tuple(result)


def _preparation_state(*, policies, decisions):
    acceptable = [decision for decision in decisions if decision.acceptable]
    direct = [
        decision
        for decision in acceptable
        if not decision.confirmation_required and TrustedReuseReasonCode.HUMAN_REVIEW_REQUIRED not in decision.reasons
    ]
    if direct:
        return PreparedRequirementState.READY, PREPARED_READY_REASON
    review = [
        decision
        for decision in acceptable
        if not decision.confirmation_required and TrustedReuseReasonCode.HUMAN_REVIEW_REQUIRED in decision.reasons
    ]
    if review:
        return PreparedRequirementState.REVIEW_REQUIRED, PREPARED_REVIEW_REASON
    if acceptable:
        return PreparedRequirementState.CONFIRMATION_REQUIRED, PREPARED_CONFIRM_REASON
    if not policies or any(decision.decision == TrustedReuseDecisionCode.UNKNOWN for decision in decisions):
        return PreparedRequirementState.UNKNOWN, PREPARED_UNKNOWN_REASON
    return PreparedRequirementState.MISSING, PREPARED_MISSING_REASON


def _readiness_check(requirement, state, reason_code):
    if state == PreparedRequirementState.READY:
        check_state = ReadinessCheckState.SATISFIED
        summary = "Un élément connu est explicitement acceptable pour cette exigence."
        action = None
    elif state == PreparedRequirementState.REVIEW_REQUIRED:
        check_state = ReadinessCheckState.WAITING
        summary = "Un élément réutilisable est connu, mais une revue humaine restera nécessaire."
        action = None
    elif state == PreparedRequirementState.CONFIRMATION_REQUIRED:
        check_state = ReadinessCheckState.ACTION_REQUIRED
        summary = "Un élément réutilisable existe, mais sa transmission exigera une confirmation explicite."
        action = NextAction(key="confirm_reuse", label="Confirmer la réutilisation au démarrage", source="prepared_start")
    elif state == PreparedRequirementState.MISSING:
        check_state = ReadinessCheckState.ACTION_REQUIRED
        summary = "Aucun élément actuellement connu n'est acceptable pour cette exigence."
        action = NextAction(key="prepare_requirement", label="Préparer cet élément", source="prepared_start")
    else:
        check_state = ReadinessCheckState.ACTION_REQUIRED
        summary = "Makolo ne peut pas encore conclure de façon fiable pour cette exigence."
        action = NextAction(key="verify_requirement", label="Vérifier cette exigence", source="prepared_start")

    return ReadinessCheck(
        key=f"prepared_requirement:{requirement.pk}",
        source="prepared_start",
        state=check_state,
        blocking=bool(requirement.is_mandatory and state != PreparedRequirementState.READY),
        reason_code=reason_code,
        summary=summary,
        next_action=action,
    )


def _requirement_result(*, requirement, memory, context, observed_at):
    policies = tuple(requirement.reuse_policies.all())
    decisions = tuple(
        evaluate_trusted_reuse_candidate(
            requirement=requirement,
            candidate=item.candidate,
            expected_subject_type=_subject_type(context),
            expected_subject_id=context.subject_id,
            source_date=item.source_date,
            observed_at=observed_at,
            policies=policies,
        )
        for item in memory
    )
    state, reason_code = _preparation_state(policies=policies, decisions=decisions)
    visible_decisions = tuple(
        decision
        for decision in decisions
        if decision.acceptable or decision.decision == TrustedReuseDecisionCode.UNKNOWN
    )
    return PreparedRequirementResult(
        requirement_id=str(requirement.pk),
        kind=requirement.kind,
        title=requirement.title,
        mandatory=bool(requirement.is_mandatory),
        position=requirement.position,
        assessment_state=RequirementAssessmentState.UNASSESSED,
        preparation_state=state,
        readiness_check=_readiness_check(requirement, state, reason_code),
        reason_codes=(reason_code, *_unique_reason_codes(decisions)),
        reuse_options=tuple(_option(decision) for decision in visible_decisions),
    )


def _readiness(requirements, *, observed_at):
    mandatory = [item for item in requirements if item.mandatory]
    checks = tuple(item.readiness_check for item in requirements)
    action_checks = [item.readiness_check for item in mandatory if item.readiness_check.state == ReadinessCheckState.ACTION_REQUIRED]
    waiting_checks = [item.readiness_check for item in mandatory if item.readiness_check.state == ReadinessCheckState.WAITING]
    if action_checks:
        status = ReadinessStatus.ACTION_REQUIRED
        next_action = next((check.next_action for check in action_checks if check.next_action is not None), None)
    elif waiting_checks:
        status = ReadinessStatus.WAITING
        next_action = None
    else:
        status = ReadinessStatus.READY
        next_action = None
    return ReadinessResult(status=status, checks=checks, next_action=next_action, observed_at=observed_at)


def prepared_start_for_revision(
    *,
    actor,
    revision,
    viewer=None,
    subject=None,
    controller=None,
    beneficiary=None,
    initiator=None,
    observed_at=None,
) -> PreparedStartResult:
    """Project one exact published OpportunityRevision before Journey materialization.

    The projection composes Q3 authorized candidate facts with Q4 exact acceptance
    policies. It never creates a Journey, Assessment, Evidence, PersonalAssetUse,
    RequirementReuseApplication or any other business row. Assessment truth remains
    UNASSESSED until an owner domain materializes and evaluates the real Journey.
    """

    observed_at = observed_at or timezone.now()
    if not isinstance(observed_at, datetime) or not timezone.is_aware(observed_at):
        raise ValidationError("observed_at doit être un datetime timezone-aware.")

    subject, context = _authorize_context(
        actor=actor,
        viewer=viewer,
        subject=subject,
        controller=controller,
        beneficiary=beneficiary,
        initiator=initiator,
    )

    revision = (
        OpportunityRevision.objects.select_related("opportunity")
        .prefetch_related(
            Prefetch(
                "requirements",
                queryset=OpportunityRequirement.objects.prefetch_related(
                    Prefetch("reuse_policies", queryset=RequirementReusePolicy.objects.order_by("key", "id"))
                ).order_by("position", "created_at", "id"),
            )
        )
        .get(pk=revision.pk)
    )
    opportunity = revision.opportunity
    if opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED:
        raise ValidationError("Prepared Start exige une Opportunity actuellement publiée.")
    if revision.published_at is None:
        raise ValidationError("Prepared Start exige une OpportunityRevision publiée.")

    memory = prepared_action_memory_for_subject(actor=actor, subject=subject, observed_at=observed_at)
    requirements = tuple(
        _requirement_result(requirement=requirement, memory=memory, context=context, observed_at=observed_at)
        for requirement in revision.requirements.all()
    )

    state_counts = {state: 0 for state in PreparedRequirementState}
    for item in requirements:
        state_counts[item.preparation_state] += 1

    return PreparedStartResult(
        context=context,
        opportunity_id=str(opportunity.pk),
        revision_id=str(revision.pk),
        revision_version=revision.version,
        observed_at=observed_at,
        readiness=_readiness(requirements, observed_at=observed_at),
        requirements=requirements,
        summary=PreparedStartSummary(
            total_requirements=len(requirements),
            mandatory_requirements=sum(1 for item in requirements if item.mandatory),
            ready_requirements=state_counts[PreparedRequirementState.READY],
            review_required_requirements=state_counts[PreparedRequirementState.REVIEW_REQUIRED],
            confirmation_required_requirements=state_counts[PreparedRequirementState.CONFIRMATION_REQUIRED],
            unknown_requirements=state_counts[PreparedRequirementState.UNKNOWN],
            missing_requirements=state_counts[PreparedRequirementState.MISSING],
        ),
    )


def revalidate_prepared_start_revision(result: PreparedStartResult, *, observed_at=None) -> PreparedRevisionRevalidation:
    """Re-read the current Opportunity revision pointer before a future action."""

    if not isinstance(result, PreparedStartResult):
        raise ValidationError("Prepared Start result invalide.")
    observed_at = observed_at or timezone.now()
    if not isinstance(observed_at, datetime) or not timezone.is_aware(observed_at):
        raise ValidationError("observed_at doit être un datetime timezone-aware.")

    opportunity = Opportunity.objects.select_related("current_revision").get(pk=result.opportunity_id)
    current = opportunity.current_revision
    current_version = current.version if current is not None and current.published_at is not None else None
    current_id = str(current.pk) if current is not None and current.published_at is not None else None
    return PreparedRevisionRevalidation(
        opportunity_id=str(opportunity.pk),
        observed_revision_id=result.revision_id,
        observed_revision_version=result.revision_version,
        current_revision_id=current_id,
        current_revision_version=current_version,
        is_current_revision=current_id == result.revision_id,
        has_newer_revision=bool(current_version is not None and current_version > result.revision_version),
        opportunity_publication_status=opportunity.publication_status,
        observed_at=observed_at,
    )
