from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifact
from journeys.collaboration_services import ensure_case_access, is_beneficiary
from journeys.models import TERMINAL_JOURNEY_STATUSES
from personal_assets.action_memory import (
    ActionMemoryCandidate,
    ActionMemoryMaterializationPath,
    ActionMemorySource,
    ActionMemorySubjectType,
    action_memory_for_journey,
)
from personal_assets.models import PersonalAssetUse, PersonalAssetVersion
from personal_assets.services import save_journey_artifact_to_library, use_personal_asset_version_in_journey
from requirements.models import RequirementReuseApplication, RequirementReusePolicy, RequirementReuseSource
from requirements.reuse_evaluator import evaluate_trusted_reuse_candidate
from requirements.trusted_reuse import TrustedReuseDecision
from trust.models import Proof, ProofStatus

from .models import ServiceRequirementAssessment
from .requirement_services import SATISFIED_REQUIREMENT_STATUSES, submit_requirement_evidence


def _enum_value(value):
    return getattr(value, "value", value)


def evaluate_trusted_reuse(*, assessment, candidate: ActionMemoryCandidate, actor, observed_at=None):
    """Evaluate one current Action Memory candidate without any business mutation.

    Services owns target Journey authorization. The acceptance rules themselves are
    delegated to the Requirements-owned Q4 evaluator also consumed by Prepared Start.
    """

    if not getattr(actor, "is_authenticated", False) or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Trusted Reuse exige un acteur authentifié.")
    observed_at = observed_at or timezone.now()
    assessment = (
        ServiceRequirementAssessment.objects.select_related(
            "requirement",
            "requirement__revision",
            "context",
            "context__journey",
            "context__journey__activity",
        )
        .get(pk=assessment.pk)
    )
    journey = assessment.context.journey
    ensure_case_access(actor, journey, write=False)

    if journey.beneficiary_id:
        subject_type = ActionMemorySubjectType.PROFILE
        subject_id = journey.beneficiary_id
    else:
        subject_type = ActionMemorySubjectType.EXTERNAL_BENEFICIARY
        subject_id = journey.external_beneficiary_id

    policies = tuple(
        RequirementReusePolicy.objects.filter(requirement_id=assessment.requirement_id).order_by("key", "id")
    )
    return evaluate_trusted_reuse_candidate(
        requirement=assessment.requirement,
        candidate=candidate,
        expected_subject_type=subject_type,
        expected_subject_id=subject_id,
        source_date=candidate.source_date,
        assessment_id=assessment.pk,
        observed_at=observed_at,
        policies=policies,
        current_requirement=(assessment.requirement.revision_id == assessment.context.opportunity_revision_id),
    )


def trusted_reuse_decisions_for_assessment(*, assessment, actor, observed_at=None):
    observed_at = observed_at or timezone.now()
    assessment = ServiceRequirementAssessment.objects.select_related("context__journey").get(pk=assessment.pk)
    candidates = action_memory_for_journey(actor=actor, journey=assessment.context.journey, observed_at=observed_at)
    return tuple(
        evaluate_trusted_reuse(
            assessment=assessment,
            candidate=candidate,
            actor=actor,
            observed_at=observed_at,
        )
        for candidate in candidates
    )


@dataclass(frozen=True)
class TrustedReuseApplicationResult:
    decision: TrustedReuseDecision
    application_id: str
    journey_artifact_id: str | None
    evidence_id: str | None
    source_asset_version_id: str | None


def _current_candidate(*, actor, journey, source, source_id, observed_at):
    for candidate in action_memory_for_journey(actor=actor, journey=journey, observed_at=observed_at):
        if _enum_value(candidate.source) == source and str(candidate.source_id) == str(source_id):
            return candidate
    raise PermissionDenied("Le candidat Trusted Reuse n’est plus disponible dans le périmètre autorisé.")


def _existing_target_use(*, version, journey):
    return (
        PersonalAssetUse.objects.filter(asset_version=version, journey_artifact__journey=journey)
        .select_related("journey_artifact")
        .order_by("used_at", "id")
        .first()
    )


def _existing_application(*, assessment, source, source_id):
    queryset = RequirementReuseApplication.objects.filter(assessment=assessment)
    if source == RequirementReuseSource.LIBRARY:
        return queryset.filter(source_asset_version_id=source_id).select_related("materialized_artifact", "evidence").first()
    if source == RequirementReuseSource.JOURNEY_ARTIFACT:
        return queryset.filter(source_journey_artifact_id=source_id).select_related("materialized_artifact", "evidence").first()
    if source == RequirementReuseSource.PROOF:
        return queryset.filter(source_proof_id=source_id).first()
    return None


def _result_from_application(application, decision):
    source_version_id = application.source_asset_version_id or application.intermediate_asset_version_id
    return TrustedReuseApplicationResult(
        decision=decision,
        application_id=str(application.pk),
        journey_artifact_id=str(application.materialized_artifact_id) if application.materialized_artifact_id else None,
        evidence_id=str(application.evidence_id) if application.evidence_id else None,
        source_asset_version_id=str(source_version_id) if source_version_id else None,
    )


def _create_application(
    *,
    assessment,
    policy,
    candidate,
    decision,
    actor,
    confirmed,
    source_asset_version=None,
    source_journey_artifact=None,
    source_proof=None,
    intermediate_asset_version=None,
    materialized_artifact=None,
    evidence=None,
):
    return RequirementReuseApplication.objects.create(
        assessment=assessment,
        policy=policy,
        source_type=_enum_value(candidate.source),
        source_asset_version=source_asset_version,
        source_journey_artifact=source_journey_artifact,
        source_proof=source_proof,
        intermediate_asset_version=intermediate_asset_version,
        decision=_enum_value(decision.decision),
        reason_codes=[_enum_value(reason) for reason in decision.reasons],
        freshness=decision.freshness or "",
        sensitivity=decision.sensitivity or "",
        source_status=candidate.status or "",
        source_version=candidate.source_version,
        confirmation_confirmed=bool(confirmed),
        materialization_path=decision.materialization_path or "",
        materialized_artifact=materialized_artifact,
        evidence=evidence,
        applied_by=actor,
        observed_at=decision.observed_at,
    )


@transaction.atomic
def apply_trusted_reuse(*, assessment, actor, candidate_source, candidate_source_id, confirmed=False):
    """Revalidate current facts then apply only through canonical owner services.

    Documents are materialized through Q2 then submitted as Services Evidence. Proof
    candidates are never converted into files: an acceptable Proof creates only the
    minimal append-only Requirement reuse audit and leaves Assessment review unchanged.
    """

    if not getattr(actor, "is_authenticated", False) or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Trusted Reuse exige un acteur authentifié.")
    assessment = (
        ServiceRequirementAssessment.objects.select_for_update(of=("self",))
        .select_related(
            "requirement",
            "requirement__revision",
            "context",
            "context__journey",
            "context__journey__activity",
        )
        .order_by()
        .get(pk=assessment.pk)
    )
    journey = assessment.context.journey
    if not is_beneficiary(actor, journey):
        ensure_case_access(actor, journey, write=True)
    if journey.status in TERMINAL_JOURNEY_STATUSES:
        raise ValidationError("Cette Journey est fermée ; aucun Trusted Reuse ne peut y être appliqué.")
    if assessment.requirement.revision_id != assessment.context.opportunity_revision_id:
        raise ValidationError("Ce Requirement appartient à une révision historique.")
    if assessment.status in SATISFIED_REQUIREMENT_STATUSES:
        raise ValidationError("Ce Requirement est déjà terminé ; aucune Evidence supplémentaire n’est créée.")

    observed_at = timezone.now()
    source = _enum_value(candidate_source)
    candidate = _current_candidate(
        actor=actor,
        journey=journey,
        source=source,
        source_id=candidate_source_id,
        observed_at=observed_at,
    )
    decision = evaluate_trusted_reuse(
        assessment=assessment,
        candidate=candidate,
        actor=actor,
        observed_at=observed_at,
    )
    if not decision.acceptable:
        raise ValidationError("Ce candidat n’est plus réutilisable dans le contexte courant.")
    if decision.confirmation_required and confirmed is not True:
        raise ValidationError("Une confirmation explicite est requise avant toute transmission de cet élément.")
    policy = RequirementReusePolicy.objects.get(pk=decision.policy_id, requirement=assessment.requirement)

    existing_application = _existing_application(
        assessment=assessment,
        source=source,
        source_id=candidate.source_id,
    )
    if existing_application is not None:
        return _result_from_application(existing_application, decision)

    if source == ActionMemorySource.PROOF.value:
        proof = Proof.objects.select_for_update(of=("self",)).order_by().filter(
            pk=candidate.source_id,
            subject_profile_id=journey.beneficiary_id,
            status=ProofStatus.ACTIVE,
        ).first()
        if proof is None:
            raise ValidationError("Cette Proof n’est plus active dans le contexte courant.")
        application = _create_application(
            assessment=assessment,
            policy=policy,
            candidate=candidate,
            decision=decision,
            actor=actor,
            confirmed=confirmed,
            source_proof=proof,
        )
        return _result_from_application(application, decision)

    source_version = None
    source_artifact = None
    primary_source_version = None
    intermediate_version = None
    if source == ActionMemorySource.LIBRARY.value:
        source_version = (
            PersonalAssetVersion.objects.select_for_update(of=("self",))
            .select_related("asset")
            .filter(
                pk=candidate.source_id,
                asset__controller=actor,
                asset__archived_at__isnull=True,
            )
            .order_by()
            .first()
        )
        if source_version is None:
            raise PermissionDenied("La version de Bibliothèque n’est plus disponible.")
        primary_source_version = source_version
    elif source == ActionMemorySource.JOURNEY_ARTIFACT.value:
        if _enum_value(candidate.materialization_path) != ActionMemoryMaterializationPath.JOURNEY_ARTIFACT_TO_PERSONAL_ASSET.value:
            raise PermissionDenied("Cet Artifact historique ne possède pas de chemin de réutilisation autorisé.")
        source_artifact = JourneyArtifact.objects.select_for_update(of=("self",)).order_by().get(pk=candidate.source_id)
        source_version = (
            PersonalAssetVersion.objects.select_for_update(of=("self",))
            .select_related("asset")
            .filter(
                source_journey_artifact=source_artifact,
                asset__controller=actor,
                asset__archived_at__isnull=True,
                asset__subject_profile_id=journey.beneficiary_id,
            )
            .order_by("created_at", "id")
            .first()
        )
        if source_version is None:
            if journey.beneficiary_id != actor.pk:
                raise PermissionDenied("Seul le bénéficiaire Profile peut conserver cet Artifact dans sa Bibliothèque.")
            source_version = save_journey_artifact_to_library(
                actor=actor,
                journey_artifact=source_artifact,
                subject_profile=journey.beneficiary,
            )
        intermediate_version = source_version
    else:
        raise ValidationError("Source Trusted Reuse non prise en charge.")

    existing_use = _existing_target_use(version=source_version, journey=journey)
    if existing_use is not None:
        artifact = existing_use.journey_artifact
    else:
        artifact = use_personal_asset_version_in_journey(
            actor=actor,
            personal_asset_version=source_version,
            journey=journey,
            title=candidate.title,
            kind=candidate.kind,
        )
    evidence = submit_requirement_evidence(assessment=assessment, artifact=artifact, actor=actor)
    application = _create_application(
        assessment=assessment,
        policy=policy,
        candidate=candidate,
        decision=decision,
        actor=actor,
        confirmed=confirmed,
        source_asset_version=primary_source_version,
        source_journey_artifact=source_artifact,
        intermediate_asset_version=intermediate_version,
        materialized_artifact=artifact,
        evidence=evidence,
    )
    return _result_from_application(application, decision)
