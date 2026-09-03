from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifactStatus, JourneyAssignmentStatus
from journeys.collaboration_services import artifacts_for_actor, ensure_case_access
from journeys.models import ExternalBeneficiary, Journey
from trust.models import ProofStatus
from trust.selectors import proofs_for_profile

from .action_memory import (
    ActionMemoryAccessState,
    ActionMemoryAction,
    ActionMemoryCandidate,
    ActionMemoryFreshness,
    ActionMemoryMaterializationPath,
    ActionMemoryProvenance,
    ActionMemoryProvenanceCode,
    ActionMemoryReasonCode,
    ActionMemoryRelevance,
    ActionMemorySource,
    ActionMemorySubject,
    ActionMemorySubjectType,
    _dedupe_explicit_snapshots,
    _freshness_for_version,
    _sensitivity_reasons,
)
from .models import PersonalAssetUse, PersonalAssetVersion
from .selectors import personal_assets_for_controller


@dataclass(frozen=True)
class PreparedActionMemoryCandidate:
    candidate: ActionMemoryCandidate
    source_date: date | None


def _subject(actor, subject):
    if not getattr(actor, "is_authenticated", False) or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Prepared Action Memory exige un Profile authentifié.")
    subject = subject or actor
    User = get_user_model()
    if isinstance(subject, User):
        if subject.pk != actor.pk:
            raise PermissionDenied("Prepared Action Memory n'ouvre pas l'historique d'un autre Profile.")
        return subject, ActionMemorySubject(ActionMemorySubjectType.PROFILE, str(subject.pk))
    if isinstance(subject, ExternalBeneficiary):
        if subject.created_by_id != actor.pk:
            raise PermissionDenied("Ce bénéficiaire externe n'appartient pas au périmètre contrôlé.")
        return subject, ActionMemorySubject(ActionMemorySubjectType.EXTERNAL_BENEFICIARY, str(subject.pk))
    raise ValidationError("Prepared Action Memory exige un Profile ou ExternalBeneficiary explicite.")


def _library_candidates(*, actor, subject, subject_ref, observed_at):
    assets = personal_assets_for_controller(actor)
    if subject_ref.subject_type == ActionMemorySubjectType.PROFILE:
        assets = assets.filter(subject_profile_id=subject.pk)
    else:
        assets = assets.filter(subject_external_beneficiary_id=subject.pk)
    assets = assets.prefetch_related(
        Prefetch(
            "versions",
            queryset=PersonalAssetVersion.objects.order_by("-version", "-created_at", "id"),
            to_attr="prepared_versions",
        )
    ).order_by("created_at", "id")

    result = []
    for asset in assets:
        versions = asset.prepared_versions
        if not versions:
            continue
        version = versions[0]
        freshness, freshness_reasons = _freshness_for_version(version, observed_at=observed_at)
        confirmation_required, sensitivity_reasons = _sensitivity_reasons(ActionMemorySource.LIBRARY, asset.sensitivity)
        if freshness == ActionMemoryFreshness.EXPIRED:
            action = ActionMemoryAction.REVIEW_LIBRARY
            path = ActionMemoryMaterializationPath.NONE
        else:
            action = ActionMemoryAction.USE_IN_JOURNEY
            path = ActionMemoryMaterializationPath.PERSONAL_ASSET_VERSION_TO_JOURNEY_ARTIFACT
        source_artifact_id = version.source_journey_artifact_id
        candidate = ActionMemoryCandidate(
            source=ActionMemorySource.LIBRARY,
            source_id=str(version.pk),
            parent_source_id=str(asset.pk),
            subject=subject_ref,
            provenance=ActionMemoryProvenance(
                code=(ActionMemoryProvenanceCode.LIBRARY_FROM_JOURNEY if source_artifact_id else ActionMemoryProvenanceCode.LIBRARY),
                journey_id=str(version.source_journey_artifact.journey_id) if source_artifact_id else None,
                related_source_id=str(source_artifact_id) if source_artifact_id else None,
            ),
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
            materialization_path=path,
            observed_at=observed_at,
        )
        result.append(PreparedActionMemoryCandidate(candidate=candidate, source_date=version.issued_at))
    return result


def _historical_journeys(*, actor, subject_ref):
    journeys = Journey.objects.select_related("activity", "beneficiary", "external_beneficiary").order_by("-updated_at", "-created_at", "id")
    if subject_ref.subject_type == ActionMemorySubjectType.PROFILE:
        journeys = journeys.filter(beneficiary_id=subject_ref.source_id)
        if str(actor.pk) != str(subject_ref.source_id):
            journeys = journeys.filter(assignments__profile_id=actor.pk, assignments__status=JourneyAssignmentStatus.ACTIVE)
    else:
        journeys = journeys.filter(
            external_beneficiary_id=subject_ref.source_id,
            assignments__profile_id=actor.pk,
            assignments__status=JourneyAssignmentStatus.ACTIVE,
        )
    return list(journeys.distinct())


def _artifact_candidates(*, actor, subject_ref, journeys, observed_at):
    actor_is_subject = subject_ref.subject_type == ActionMemorySubjectType.PROFILE and str(actor.pk) == str(subject_ref.source_id)
    result = []
    for journey in journeys:
        try:
            artifacts = list(
                artifacts_for_actor(actor=actor, journey=journey)
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
            ).select_related("asset_version").order_by("used_at", "id")
        }
        for artifact in artifacts:
            confirmation_required, sensitivity_reasons = _sensitivity_reasons(ActionMemorySource.JOURNEY_ARTIFACT, artifact.sensitivity)
            use = uses.get(str(artifact.pk))
            provenance = ActionMemoryProvenance(
                code=ActionMemoryProvenanceCode.JOURNEY_FROM_LIBRARY if use else ActionMemoryProvenanceCode.JOURNEY,
                journey_id=str(journey.pk),
                related_source_id=str(use.asset_version_id) if use else None,
            )
            candidate = ActionMemoryCandidate(
                source=ActionMemorySource.JOURNEY_ARTIFACT,
                source_id=str(artifact.pk),
                parent_source_id=str(journey.pk),
                subject=subject_ref,
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
                action=ActionMemoryAction.SAVE_TO_LIBRARY if actor_is_subject else ActionMemoryAction.NONE,
                materialization_path=(
                    ActionMemoryMaterializationPath.JOURNEY_ARTIFACT_TO_PERSONAL_ASSET
                    if actor_is_subject
                    else ActionMemoryMaterializationPath.NONE
                ),
                observed_at=observed_at,
            )
            source_date = timezone.localdate(artifact.uploaded_at) if timezone.is_aware(artifact.uploaded_at) else artifact.uploaded_at.date()
            result.append(PreparedActionMemoryCandidate(candidate=candidate, source_date=source_date))
    return result


def _proof_candidates(*, actor, subject, subject_ref, journeys, observed_at):
    if subject_ref.subject_type != ActionMemorySubjectType.PROFILE:
        return []
    journey_ids = {journey.pk for journey in journeys}
    result = []
    for proof in proofs_for_profile(subject).filter(journey_id__in=journey_ids):
        try:
            ensure_case_access(actor, proof.journey, write=False)
        except PermissionDenied:
            continue
        active = proof.status == ProofStatus.ACTIVE
        candidate = ActionMemoryCandidate(
            source=ActionMemorySource.PROOF,
            source_id=str(proof.pk),
            parent_source_id=str(proof.journey_id),
            subject=subject_ref,
            provenance=ActionMemoryProvenance(code=ActionMemoryProvenanceCode.PROOF, journey_id=str(proof.journey_id)),
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
            action=ActionMemoryAction.VIEW_PROOF if str(actor.pk) == str(subject_ref.source_id) else ActionMemoryAction.NONE,
            materialization_path=(
                ActionMemoryMaterializationPath.TRUST_PROOF_VIEW
                if str(actor.pk) == str(subject_ref.source_id)
                else ActionMemoryMaterializationPath.NONE
            ),
            observed_at=observed_at,
        )
        source_date = timezone.localdate(proof.issued_at) if timezone.is_aware(proof.issued_at) else proof.issued_at.date()
        result.append(PreparedActionMemoryCandidate(candidate=candidate, source_date=source_date))
    return result


def prepared_action_memory_for_subject(*, actor, subject=None, observed_at=None):
    """Return authorized Q3 candidate facts before a target Journey exists.

    This is read-only. It does not materialize a Journey, copy a file, create an
    Evidence, apply Trusted Reuse or change Readiness. Target-Journey permissions
    are intentionally deferred and revalidated when a Journey is later created.
    """

    observed_at = observed_at or timezone.now()
    if not timezone.is_aware(observed_at):
        raise ValidationError("observed_at doit être timezone-aware.")
    subject, subject_ref = _subject(actor, subject)
    library = _library_candidates(actor=actor, subject=subject, subject_ref=subject_ref, observed_at=observed_at)
    journeys = _historical_journeys(actor=actor, subject_ref=subject_ref)
    artifacts = _artifact_candidates(actor=actor, subject_ref=subject_ref, journeys=journeys, observed_at=observed_at)
    deduped = _dedupe_explicit_snapshots([item.candidate for item in library], [item.candidate for item in artifacts])
    deduped_ids = {(candidate.source, candidate.source_id) for candidate in deduped}
    artifacts = [item for item in artifacts if (item.candidate.source, item.candidate.source_id) in deduped_ids]
    proofs = _proof_candidates(actor=actor, subject=subject, subject_ref=subject_ref, journeys=journeys, observed_at=observed_at)
    return tuple((*library, *artifacts, *proofs))
