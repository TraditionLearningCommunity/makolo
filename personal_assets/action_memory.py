from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from journeys.collaboration_models import (
    JourneyArtifactSensitivity,
    JourneyArtifactStatus,
    JourneyAssignmentStatus,
)
from journeys.collaboration_services import (
    artifacts_for_actor,
    can_access_case,
    ensure_case_access,
    is_beneficiary,
)
from journeys.models import ExternalBeneficiary, Journey
from trust.models import ProofStatus
from trust.selectors import proofs_for_profile

from .models import PersonalAssetUse
from .selectors import personal_asset_versions_for_controller, personal_assets_for_controller


class ActionMemorySource(str, Enum):
    LIBRARY = "library"
    JOURNEY_ARTIFACT = "journey_artifact"
    PROOF = "proof"


class ActionMemorySubjectType(str, Enum):
    PROFILE = "profile"
    EXTERNAL_BENEFICIARY = "external_beneficiary"


class ActionMemoryProvenanceCode(str, Enum):
    LIBRARY = "library"
    LIBRARY_FROM_JOURNEY = "library.from_journey"
    JOURNEY = "journey"
    JOURNEY_FROM_LIBRARY = "journey.from_library"
    PROOF = "proof"


class ActionMemoryFreshness(str, Enum):
    NOT_EXPIRED = "not_expired"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ActionMemoryRelevance(str, Enum):
    POTENTIALLY_RELEVANT = "potentially_relevant"


class ActionMemoryAccessState(str, Enum):
    ALLOWED_TO_PROPOSE = "allowed_to_propose"


class ActionMemoryAction(str, Enum):
    USE_IN_JOURNEY = "use_in_journey"
    REVIEW_LIBRARY = "review_library"
    SAVE_TO_LIBRARY = "save_to_library"
    VIEW_PROOF = "view_proof"
    NONE = "none"


class ActionMemoryMaterializationPath(str, Enum):
    PERSONAL_ASSET_VERSION_TO_JOURNEY_ARTIFACT = "personal_asset_version_to_journey_artifact"
    JOURNEY_ARTIFACT_TO_PERSONAL_ASSET = "journey_artifact_to_personal_asset"
    TRUST_PROOF_VIEW = "trust_proof_view"
    NONE = "none"


class ActionMemoryReasonCode(str, Enum):
    SUBJECT_MATCH = "subject.match"
    LIBRARY_AVAILABLE = "library.available"
    LIBRARY_CURRENT_VERSION = "library.current_version"
    LIBRARY_EXPIRED = "library.expired"
    LIBRARY_SENSITIVE = "library.sensitive"
    LIBRARY_RESTRICTED = "library.restricted"
    JOURNEY_PREVIOUS_ARTIFACT = "journey.previous_artifact"
    JOURNEY_SENSITIVE = "journey.sensitive"
    JOURNEY_RESTRICTED = "journey.restricted"
    PROOF_ACTIVE = "proof.active"
    PROOF_REVOKED = "proof.revoked"
    FRESHNESS_NOT_EXPIRED = "freshness.not_expired"
    FRESHNESS_EXPIRED = "freshness.expired"
    FRESHNESS_UNKNOWN = "freshness.unknown"
    CONFIRMATION_REQUIRED = "confirmation.required"


@dataclass(frozen=True)
class ActionMemorySubject:
    subject_type: ActionMemorySubjectType
    source_id: str


@dataclass(frozen=True)
class ActionMemoryProvenance:
    code: ActionMemoryProvenanceCode
    journey_id: str | None = None
    related_source_id: str | None = None


@dataclass(frozen=True)
class ActionMemoryCandidate:
    source: ActionMemorySource
    source_id: str
    parent_source_id: str | None
    subject: ActionMemorySubject
    provenance: ActionMemoryProvenance
    kind: str | None
    title: str
    status: str | None
    source_version: int | None
    relevant_at: date | datetime | None
    freshness: ActionMemoryFreshness
    expires_at: date | None
    sensitivity: str | None
    content_hash: str | None
    relevance: ActionMemoryRelevance
    access_state: ActionMemoryAccessState
    reasons: tuple[ActionMemoryReasonCode, ...]
    confirmation_required: bool
    action: ActionMemoryAction
    materialization_path: ActionMemoryMaterializationPath
    observed_at: datetime
    source_date: date | None = None


def _authenticated(actor) -> bool:
    return bool(getattr(actor, "is_authenticated", False) and getattr(actor, "pk", None))


def _subject_for_journey(journey) -> ActionMemorySubject:
    if journey.beneficiary_id:
        return ActionMemorySubject(ActionMemorySubjectType.PROFILE, str(journey.beneficiary_id))
    if journey.external_beneficiary_id:
        return ActionMemorySubject(
            ActionMemorySubjectType.EXTERNAL_BENEFICIARY,
            str(journey.external_beneficiary_id),
        )
    raise ValidationError("Action Memory exige une Journey avec un bénéficiaire explicite.")


def _subject_for_preparation(*, actor, subject):
    User = get_user_model()
    if isinstance(subject, User):
        if subject.pk != actor.pk:
            raise PermissionDenied("Prepared Action Memory n'ouvre pas l'historique d'un autre Profile.")
        return ActionMemorySubject(ActionMemorySubjectType.PROFILE, str(subject.pk)), subject
    if isinstance(subject, ExternalBeneficiary):
        if subject.created_by_id != actor.pk:
            raise PermissionDenied("Ce bénéficiaire externe n'appartient pas au périmètre contrôlé.")
        return ActionMemorySubject(ActionMemorySubjectType.EXTERNAL_BENEFICIARY, str(subject.pk)), None
    raise ValidationError("Prepared Action Memory exige un Profile ou ExternalBeneficiary explicite.")


def _asset_matches_subject(asset, subject: ActionMemorySubject) -> bool:
    if subject.subject_type == ActionMemorySubjectType.PROFILE:
        return str(asset.subject_profile_id or "") == subject.source_id
    return str(asset.subject_external_beneficiary_id or "") == subject.source_id


def _freshness_for_version(version, *, observed_at):
    if version.expires_at is None:
        return ActionMemoryFreshness.UNKNOWN, (ActionMemoryReasonCode.FRESHNESS_UNKNOWN,)
    observed_date = (
        timezone.localdate(observed_at)
        if timezone.is_aware(observed_at)
        else observed_at.date()
    )
    if version.expires_at < observed_date:
        return ActionMemoryFreshness.EXPIRED, (
            ActionMemoryReasonCode.LIBRARY_EXPIRED,
            ActionMemoryReasonCode.FRESHNESS_EXPIRED,
        )
    return ActionMemoryFreshness.NOT_EXPIRED, (ActionMemoryReasonCode.FRESHNESS_NOT_EXPIRED,)


def _sensitivity_reasons(source, sensitivity):
    if sensitivity == JourneyArtifactSensitivity.SENSITIVE:
        reason = (
            ActionMemoryReasonCode.LIBRARY_SENSITIVE
            if source == ActionMemorySource.LIBRARY
            else ActionMemoryReasonCode.JOURNEY_SENSITIVE
        )
        return True, (reason, ActionMemoryReasonCode.CONFIRMATION_REQUIRED)
    if sensitivity == JourneyArtifactSensitivity.RESTRICTED:
        reason = (
            ActionMemoryReasonCode.LIBRARY_RESTRICTED
            if source == ActionMemorySource.LIBRARY
            else ActionMemoryReasonCode.JOURNEY_RESTRICTED
        )
        return True, (reason, ActionMemoryReasonCode.CONFIRMATION_REQUIRED)
    return False, ()


def _can_materialize_library_version(*, actor, journey, sensitivity) -> bool:
    if is_beneficiary(actor, journey):
        return True
    return can_access_case(
        actor,
        journey,
        write=True,
        restricted=sensitivity == JourneyArtifactSensitivity.RESTRICTED,
    )


def _library_candidates(*, actor, subject, observed_at, target_journey=None):
    candidates = []
    for asset in personal_assets_for_controller(actor):
        if not _asset_matches_subject(asset, subject):
            continue
        version = (
            personal_asset_versions_for_controller(actor, asset)
            .select_related("source_journey_artifact")
            .order_by("-version", "-created_at")
            .first()
        )
        if version is None:
            continue

        freshness, freshness_reasons = _freshness_for_version(version, observed_at=observed_at)
        confirmation_required, sensitivity_reasons = _sensitivity_reasons(
            ActionMemorySource.LIBRARY,
            asset.sensitivity,
        )
        can_use = (
            True
            if target_journey is None
            else _can_materialize_library_version(
                actor=actor,
                journey=target_journey,
                sensitivity=asset.sensitivity,
            )
        )
        if freshness == ActionMemoryFreshness.EXPIRED or not can_use:
            action = ActionMemoryAction.REVIEW_LIBRARY
            materialization_path = ActionMemoryMaterializationPath.NONE
        else:
            action = ActionMemoryAction.USE_IN_JOURNEY
            materialization_path = ActionMemoryMaterializationPath.PERSONAL_ASSET_VERSION_TO_JOURNEY_ARTIFACT

        source_artifact_id = version.source_journey_artifact_id
        provenance = ActionMemoryProvenance(
            code=(
                ActionMemoryProvenanceCode.LIBRARY_FROM_JOURNEY
                if source_artifact_id
                else ActionMemoryProvenanceCode.LIBRARY
            ),
            journey_id=(
                str(version.source_journey_artifact.journey_id)
                if source_artifact_id
                else None
            ),
            related_source_id=str(source_artifact_id) if source_artifact_id else None,
        )
        candidates.append(
            ActionMemoryCandidate(
                source=ActionMemorySource.LIBRARY,
                source_id=str(version.pk),
                parent_source_id=str(asset.pk),
                subject=subject,
                provenance=provenance,
                kind=asset.kind,
                title=asset.title,
                status="current_version",
                source_version=version.version,
                relevant_at=version.issued_at or version.created_at,
                freshness=freshness,
                expires_at=version.expires_at,
                sensitivity=asset.sensitivity,
                content_hash=version.content_hash,
                relevance=ActionMemoryRelevance.POTENTIALLY_RELEVANT,
                access_state=ActionMemoryAccessState.ALLOWED_TO_PROPOSE,
                reasons=(
                    ActionMemoryReasonCode.SUBJECT_MATCH,
                    ActionMemoryReasonCode.LIBRARY_AVAILABLE,
                    ActionMemoryReasonCode.LIBRARY_CURRENT_VERSION,
                    *freshness_reasons,
                    *sensitivity_reasons,
                ),
                confirmation_required=confirmation_required,
                action=action,
                materialization_path=materialization_path,
                observed_at=observed_at,
                source_date=version.issued_at,
            )
        )
    return candidates


def _historical_journeys(*, actor, subject, exclude_journey=None):
    queryset = Journey.objects.select_related("activity", "beneficiary", "external_beneficiary").order_by(
        "-updated_at", "-created_at", "id"
    )
    if exclude_journey is not None:
        queryset = queryset.exclude(pk=exclude_journey.pk)
    if subject.subject_type == ActionMemorySubjectType.PROFILE:
        queryset = queryset.filter(beneficiary_id=subject.source_id)
        if str(getattr(actor, "pk", "")) != subject.source_id:
            queryset = queryset.filter(
                assignments__profile_id=actor.pk,
                assignments__status=JourneyAssignmentStatus.ACTIVE,
            )
    else:
        queryset = queryset.filter(
            external_beneficiary_id=subject.source_id,
            assignments__profile_id=actor.pk,
            assignments__status=JourneyAssignmentStatus.ACTIVE,
        )
    return list(queryset.distinct())


def _journey_artifact_candidates(*, actor, subject, historical_journeys, observed_at):
    candidates = []
    actor_is_subject = bool(
        subject.subject_type == ActionMemorySubjectType.PROFILE
        and str(getattr(actor, "pk", "")) == subject.source_id
    )
    for historical_journey in historical_journeys:
        try:
            artifacts = list(
                artifacts_for_actor(actor=actor, journey=historical_journey)
                .exclude(status=JourneyArtifactStatus.SUPERSEDED)
                .order_by("-uploaded_at", "-created_at", "id")
            )
        except PermissionDenied:
            continue
        uses = {
            str(use.journey_artifact_id): use
            for use in PersonalAssetUse.objects.filter(
                journey_artifact__in=artifacts,
                asset_version__asset__controller=actor,
            )
            .select_related("asset_version")
            .order_by("used_at", "id")
        }
        for artifact in artifacts:
            confirmation_required, sensitivity_reasons = _sensitivity_reasons(
                ActionMemorySource.JOURNEY_ARTIFACT,
                artifact.sensitivity,
            )
            use = uses.get(str(artifact.pk))
            if use:
                provenance = ActionMemoryProvenance(
                    code=ActionMemoryProvenanceCode.JOURNEY_FROM_LIBRARY,
                    journey_id=str(historical_journey.pk),
                    related_source_id=str(use.asset_version_id),
                )
            else:
                provenance = ActionMemoryProvenance(
                    code=ActionMemoryProvenanceCode.JOURNEY,
                    journey_id=str(historical_journey.pk),
                )
            action = ActionMemoryAction.SAVE_TO_LIBRARY if actor_is_subject else ActionMemoryAction.NONE
            materialization_path = (
                ActionMemoryMaterializationPath.JOURNEY_ARTIFACT_TO_PERSONAL_ASSET
                if action == ActionMemoryAction.SAVE_TO_LIBRARY
                else ActionMemoryMaterializationPath.NONE
            )
            source_date = (
                timezone.localdate(artifact.uploaded_at)
                if timezone.is_aware(artifact.uploaded_at)
                else artifact.uploaded_at.date()
            )
            candidates.append(
                ActionMemoryCandidate(
                    source=ActionMemorySource.JOURNEY_ARTIFACT,
                    source_id=str(artifact.pk),
                    parent_source_id=str(historical_journey.pk),
                    subject=subject,
                    provenance=provenance,
                    kind=artifact.kind,
                    title=artifact.title,
                    status=artifact.status,
                    source_version=artifact.version,
                    relevant_at=artifact.uploaded_at,
                    freshness=ActionMemoryFreshness.UNKNOWN,
                    expires_at=None,
                    sensitivity=artifact.sensitivity,
                    content_hash=artifact.content_hash,
                    relevance=ActionMemoryRelevance.POTENTIALLY_RELEVANT,
                    access_state=ActionMemoryAccessState.ALLOWED_TO_PROPOSE,
                    reasons=(
                        ActionMemoryReasonCode.SUBJECT_MATCH,
                        ActionMemoryReasonCode.JOURNEY_PREVIOUS_ARTIFACT,
                        ActionMemoryReasonCode.FRESHNESS_UNKNOWN,
                        *sensitivity_reasons,
                    ),
                    confirmation_required=confirmation_required,
                    action=action,
                    materialization_path=materialization_path,
                    observed_at=observed_at,
                    source_date=source_date,
                )
            )
    return candidates


def _proof_candidates(*, actor, subject, subject_profile, historical_journeys, observed_at):
    if subject.subject_type != ActionMemorySubjectType.PROFILE or subject_profile is None:
        return []
    historical_ids = [journey.pk for journey in historical_journeys]
    if not historical_ids:
        return []
    actor_is_subject = str(getattr(actor, "pk", "")) == subject.source_id
    candidates = []
    proofs = proofs_for_profile(subject_profile).filter(journey_id__in=historical_ids)
    for proof in proofs:
        try:
            ensure_case_access(actor, proof.journey, write=False)
        except PermissionDenied:
            continue
        active = proof.status == ProofStatus.ACTIVE
        action = ActionMemoryAction.VIEW_PROOF if actor_is_subject else ActionMemoryAction.NONE
        source_date = (
            timezone.localdate(proof.issued_at)
            if timezone.is_aware(proof.issued_at)
            else proof.issued_at.date()
        )
        candidates.append(
            ActionMemoryCandidate(
                source=ActionMemorySource.PROOF,
                source_id=str(proof.pk),
                parent_source_id=str(proof.journey_id),
                subject=subject,
                provenance=ActionMemoryProvenance(
                    code=ActionMemoryProvenanceCode.PROOF,
                    journey_id=str(proof.journey_id),
                ),
                kind=proof.proof_type,
                title=proof.get_proof_type_display(),
                status=proof.status,
                source_version=None,
                relevant_at=proof.revoked_at or proof.issued_at,
                freshness=ActionMemoryFreshness.UNKNOWN,
                expires_at=None,
                sensitivity=None,
                content_hash=None,
                relevance=ActionMemoryRelevance.POTENTIALLY_RELEVANT,
                access_state=ActionMemoryAccessState.ALLOWED_TO_PROPOSE,
                reasons=(
                    ActionMemoryReasonCode.SUBJECT_MATCH,
                    ActionMemoryReasonCode.PROOF_ACTIVE if active else ActionMemoryReasonCode.PROOF_REVOKED,
                    ActionMemoryReasonCode.FRESHNESS_UNKNOWN,
                ),
                confirmation_required=False,
                action=action,
                materialization_path=(
                    ActionMemoryMaterializationPath.TRUST_PROOF_VIEW
                    if action == ActionMemoryAction.VIEW_PROOF
                    else ActionMemoryMaterializationPath.NONE
                ),
                observed_at=observed_at,
                source_date=source_date,
            )
        )
    return candidates


def _dedupe_explicit_snapshots(library_candidates, artifact_candidates):
    """Drop only exact Q2 copies whose provenance and hash both agree.

    Matching hashes without an explicit Q2 provenance edge are intentionally kept
    as separate business objects: identical payload does not imply identical meaning.
    """

    library_by_version = {candidate.source_id: candidate for candidate in library_candidates}
    library_by_source_artifact = {
        candidate.provenance.related_source_id: candidate
        for candidate in library_candidates
        if candidate.provenance.code == ActionMemoryProvenanceCode.LIBRARY_FROM_JOURNEY
        and candidate.provenance.related_source_id
    }
    result = []
    for artifact in artifact_candidates:
        copied_to_library = library_by_source_artifact.get(artifact.source_id)
        if (
            copied_to_library is not None
            and copied_to_library.content_hash
            and copied_to_library.content_hash == artifact.content_hash
        ):
            continue
        if artifact.provenance.code == ActionMemoryProvenanceCode.JOURNEY_FROM_LIBRARY:
            source_version = library_by_version.get(artifact.provenance.related_source_id)
            if (
                source_version is not None
                and source_version.content_hash
                and source_version.content_hash == artifact.content_hash
            ):
                continue
        result.append(artifact)
    return result


def _memory_for_subject(*, actor, subject, subject_profile, observed_at, exclude_journey=None, target_journey=None):
    historical_journeys = _historical_journeys(
        actor=actor,
        subject=subject,
        exclude_journey=exclude_journey,
    )
    library = _library_candidates(
        actor=actor,
        subject=subject,
        observed_at=observed_at,
        target_journey=target_journey,
    )
    artifacts = _journey_artifact_candidates(
        actor=actor,
        subject=subject,
        historical_journeys=historical_journeys,
        observed_at=observed_at,
    )
    artifacts = _dedupe_explicit_snapshots(library, artifacts)
    proofs = _proof_candidates(
        actor=actor,
        subject=subject,
        subject_profile=subject_profile,
        historical_journeys=historical_journeys,
        observed_at=observed_at,
    )
    return tuple((*library, *artifacts, *proofs))


def action_memory_for_journey(*, actor, journey, observed_at=None):
    """Build the authorized Action Memory read model for one current Journey.

    The function is deliberately read-only. It never opens file payloads, writes a
    PersonalAsset/JourneyArtifact/Proof, evaluates a Requirement, or changes Readiness.
    Returned order is a deterministic source grouping (Library, Journey, Proof), not
    a relevance score.
    """

    if not _authenticated(actor):
        raise PermissionDenied("Action Memory exige un Profile authentifié.")
    ensure_case_access(actor, journey, write=False)
    observed_at = observed_at or timezone.now()
    subject = _subject_for_journey(journey)
    return _memory_for_subject(
        actor=actor,
        subject=subject,
        subject_profile=journey.beneficiary if journey.beneficiary_id else None,
        observed_at=observed_at,
        exclude_journey=journey,
        target_journey=journey,
    )


def action_memory_for_subject(*, actor, subject=None, observed_at=None):
    """Build authorized Q3 candidate facts before a target Journey exists.

    This read-only projection is intentionally conservative: a Profile may inspect
    its own Action Memory; an ExternalBeneficiary is available only to its creator.
    Historical Journey visibility remains governed by Journey assignments/access.
    Target-Journey write permission is not guessed here and is revalidated later by
    Q2/Q4 owner services when a real Journey exists.
    """

    if not _authenticated(actor):
        raise PermissionDenied("Prepared Action Memory exige un Profile authentifié.")
    observed_at = observed_at or timezone.now()
    if not timezone.is_aware(observed_at):
        raise ValidationError("observed_at doit être timezone-aware.")
    subject = subject or actor
    subject_ref, subject_profile = _subject_for_preparation(actor=actor, subject=subject)
    return _memory_for_subject(
        actor=actor,
        subject=subject_ref,
        subject_profile=subject_profile,
        observed_at=observed_at,
    )
