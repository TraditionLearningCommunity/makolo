from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from access.models import AccessUseResult
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import JourneyStatus, WorkflowKind
from organizations.models import OrganizationVerificationStatus

from .models import (
    Dispute,
    DisputeStatus,
    Feedback,
    FeedbackAnswer,
    Proof,
    ProofStatus,
    ProofType,
    RemedyCode,
    Report,
    ReportStatus,
    TrustEvidence,
    VerificationClaim,
    VerificationClaimType,
    VerificationDisclosure,
    VerificationStatus,
)


TERMINAL_NON_EXPERIENCE_STATUSES = {
    JourneyStatus.REJECTED,
    JourneyStatus.CANCELLED,
    JourneyStatus.EXPIRED,
}


def _authenticated(actor) -> bool:
    return bool(actor and getattr(actor, "is_authenticated", False))


def _require_authenticated(actor) -> None:
    if not _authenticated(actor):
        raise PermissionDenied("Authentification requise.")


def _require_platform_reviewer(actor) -> None:
    _require_authenticated(actor)
    if not can(actor, PermissionCode.PLATFORM_TRUST_REVIEW):
        raise PermissionDenied("Autorité Trust plateforme requise.")


def can_manage_space_trust(actor, space) -> bool:
    return _authenticated(actor) and can(actor, PermissionCode.SPACE_TRUST_MANAGE, space=space)


def can_view_space_trust(actor, space) -> bool:
    return _authenticated(actor) and (
        can(actor, PermissionCode.SPACE_TRUST_VIEW, space=space)
        or can(actor, PermissionCode.SPACE_TRUST_MANAGE, space=space)
        or can(actor, PermissionCode.PLATFORM_TRUST_REVIEW)
    )


@transaction.atomic
def request_verification(
    *,
    actor,
    claim_type,
    subject_profile=None,
    subject_space=None,
    disclosure=VerificationDisclosure.PUBLIC_RESULT,
) -> VerificationClaim:
    _require_authenticated(actor)
    if bool(subject_profile) == bool(subject_space):
        raise ValidationError("La demande doit viser exactement un Profil ou un Espace.")
    if subject_profile is not None:
        if actor.pk != subject_profile.pk:
            raise PermissionDenied("Un Profil ne peut demander une vérification que pour lui-même.")
        if claim_type not in {VerificationClaimType.PROFILE_IDENTITY, VerificationClaimType.CONTACT}:
            raise ValidationError("Ce type de claim ne s’applique pas à un Profil.")
    else:
        if not can_manage_space_trust(actor, subject_space):
            raise PermissionDenied("Un Mandate Trust de cet Espace est requis.")
        if claim_type not in {VerificationClaimType.ORGANIZATION_IDENTITY, VerificationClaimType.CONTACT}:
            raise ValidationError("Ce type de claim ne s’applique pas à un Espace.")

    active_statuses = [VerificationStatus.REQUESTED, VerificationStatus.UNDER_REVIEW, VerificationStatus.VERIFIED]
    queryset = VerificationClaim.objects.select_for_update().filter(
        claim_type=claim_type,
        status__in=active_statuses,
    )
    queryset = queryset.filter(subject_profile=subject_profile) if subject_profile else queryset.filter(subject_space=subject_space)
    for existing in queryset.order_by("-requested_at"):
        if existing.status != VerificationStatus.VERIFIED or existing.is_currently_verified:
            return existing

    claim = VerificationClaim(
        subject_profile=subject_profile,
        subject_space=subject_space,
        claim_type=claim_type,
        requested_by=actor,
        status=VerificationStatus.REQUESTED,
        disclosure=disclosure,
    )
    claim.full_clean()
    claim.save()
    if subject_space and claim_type == VerificationClaimType.ORGANIZATION_IDENTITY:
        subject_space.verification_status = OrganizationVerificationStatus.PENDING
        subject_space.save(update_fields=["verification_status", "updated_at"])
    return claim


@transaction.atomic
def start_verification_review(*, claim, actor) -> VerificationClaim:
    _require_platform_reviewer(actor)
    locked = VerificationClaim.objects.select_for_update().get(pk=claim.pk)
    if locked.requested_by_id == actor.pk or locked.subject_profile_id == actor.pk:
        raise PermissionDenied("Une personne ne peut pas examiner sa propre vérification.")
    if locked.status == VerificationStatus.UNDER_REVIEW:
        return locked
    if locked.status != VerificationStatus.REQUESTED:
        raise ValidationError("Seule une demande en attente peut passer en revue.")
    locked.status = VerificationStatus.UNDER_REVIEW
    locked.reviewed_by = actor
    locked.save(update_fields=["status", "reviewed_by", "updated_at"])
    return locked


@transaction.atomic
def decide_verification(
    *,
    claim,
    actor,
    verified: bool,
    reason_code="",
    private_note="",
    valid_from=None,
    valid_until=None,
) -> VerificationClaim:
    _require_platform_reviewer(actor)
    locked = VerificationClaim.objects.select_for_update().select_related("subject_space").get(pk=claim.pk)
    if locked.requested_by_id == actor.pk or locked.subject_profile_id == actor.pk:
        raise PermissionDenied("Une personne ne peut pas valider sa propre vérification.")
    target = VerificationStatus.VERIFIED if verified else VerificationStatus.REJECTED
    if locked.status == target:
        return locked
    if locked.status not in {VerificationStatus.REQUESTED, VerificationStatus.UNDER_REVIEW}:
        raise ValidationError("Cette vérification ne peut plus recevoir cette décision.")
    now = timezone.now()
    locked.status = target
    locked.reviewed_by = actor
    locked.reviewed_at = now
    locked.decision_reason_code = (reason_code or "").strip()
    locked.decision_note_private = (private_note or "").strip()
    if verified:
        locked.valid_from = valid_from or now
        locked.valid_until = valid_until
    else:
        locked.valid_from = None
        locked.valid_until = None
    locked.full_clean()
    locked.save()
    if locked.subject_space_id and locked.claim_type == VerificationClaimType.ORGANIZATION_IDENTITY:
        locked.subject_space.verification_status = (
            OrganizationVerificationStatus.VERIFIED if verified else OrganizationVerificationStatus.NEW
        )
        locked.subject_space.save(update_fields=["verification_status", "updated_at"])
    return locked


@transaction.atomic
def revoke_verification(*, claim, actor, reason_code, private_note="") -> VerificationClaim:
    _require_platform_reviewer(actor)
    locked = VerificationClaim.objects.select_for_update().select_related("subject_space").get(pk=claim.pk)
    if locked.status == VerificationStatus.REVOKED:
        return locked
    if locked.status != VerificationStatus.VERIFIED:
        raise ValidationError("Seule une vérification établie peut être révoquée.")
    now = timezone.now()
    locked.status = VerificationStatus.REVOKED
    locked.revoked_at = now
    locked.reviewed_by = actor
    locked.reviewed_at = now
    locked.decision_reason_code = (reason_code or "").strip()
    locked.decision_note_private = (private_note or "").strip()
    locked.save()
    if locked.subject_space_id and locked.claim_type == VerificationClaimType.ORGANIZATION_IDENTITY:
        locked.subject_space.verification_status = OrganizationVerificationStatus.SUSPENDED
        locked.subject_space.save(update_fields=["verification_status", "updated_at"])
    return locked


def can_submit_feedback(*, journey, actor, at=None) -> bool:
    if not _authenticated(actor) or journey.beneficiary_id != actor.pk:
        return False
    if journey.status in TERMINAL_NON_EXPERIENCE_STATUSES:
        return False
    if Feedback.objects.filter(journey=journey, author=actor).exists():
        return False
    if journey.status == JourneyStatus.FULFILLED:
        return True
    at = at or timezone.now()
    occurrence = journey.occurrence
    if occurrence is not None and occurrence.status == "completed":
        return True
    if occurrence is not None and occurrence.end_at and occurrence.end_at <= at:
        return True
    if journey.accesses.filter(uses__result=AccessUseResult.ACCEPTED).exists():
        return True
    try:
        service_context = journey.service_context
    except Exception:
        service_context = None
    return bool(service_context and service_context.current_outcome == "successful")


@transaction.atomic
def submit_feedback(
    *,
    journey,
    actor,
    delivery=FeedbackAnswer.NOT_APPLICABLE,
    timeliness=FeedbackAnswer.NOT_APPLICABLE,
    access_experience=FeedbackAnswer.NOT_APPLICABLE,
    accuracy=FeedbackAnswer.NOT_APPLICABLE,
    overall_sentiment="",
    comment="",
) -> Feedback:
    _require_authenticated(actor)
    if not can_submit_feedback(journey=journey, actor=actor):
        raise PermissionDenied("Cette expérience n’est pas éligible à un feedback vérifié.")
    has_access = journey.accesses.exists()
    if not has_access and access_experience != FeedbackAnswer.NOT_APPLICABLE:
        raise ValidationError({"access_experience": "Cette dimension ne s’applique pas à cette Journey."})
    feedback = Feedback(
        journey=journey,
        occurrence=journey.occurrence,
        author=actor,
        delivery=delivery,
        timeliness=timeliness,
        access_experience=access_experience,
        accuracy=accuracy,
        overall_sentiment=overall_sentiment,
        comment=(comment or "").strip(),
    )
    feedback.full_clean()
    feedback.save()
    return feedback


@transaction.atomic
def withdraw_feedback(*, feedback, actor) -> Feedback:
    locked = Feedback.objects.select_for_update().get(pk=feedback.pk)
    if locked.author_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul l’auteur peut retirer son feedback.")
    if locked.withdrawn_at is None:
        locked.withdrawn_at = timezone.now()
        locked.save(update_fields=["withdrawn_at", "updated_at"])
    return locked


@transaction.atomic
def create_report(*, actor, category, description, journey=None, access_use=None, space=None) -> Report:
    _require_authenticated(actor)
    activity = None
    occurrence = None
    if journey is not None:
        if journey.beneficiary_id != actor.pk:
            raise PermissionDenied("Le signalement doit concerner votre propre expérience Makolo.")
        activity = journey.activity
        occurrence = journey.occurrence
        space = journey.activity.space
    if access_use is not None:
        if access_use.access.beneficiary_id != actor.pk:
            raise PermissionDenied("Cet usage Access ne vous appartient pas.")
        if journey is None:
            journey = access_use.access.journey
            activity = access_use.access.activity
            occurrence = access_use.occurrence or access_use.access.occurrence
            space = activity.space
    if journey is None and access_use is None:
        if space is None:
            raise ValidationError("Un contexte vérifiable est requis pour créer un signalement.")
        if not can_view_space_trust(actor, space):
            raise PermissionDenied("Ce signalement direct d’Espace exige une autorité Trust.")
    report = Report(
        reporter=actor,
        category=category,
        description=(description or "").strip(),
        journey=journey,
        activity=activity,
        occurrence=occurrence,
        access_use=access_use,
        space=space,
    )
    report.full_clean()
    report.save()
    return report


@transaction.atomic
def triage_report(*, report, actor, investigate=True, private_note="") -> Report:
    _require_platform_reviewer(actor)
    locked = Report.objects.select_for_update().get(pk=report.pk)
    if locked.status in {ReportStatus.RESOLVED, ReportStatus.DISMISSED}:
        return locked
    locked.status = ReportStatus.INVESTIGATING if investigate else ReportStatus.TRIAGED
    locked.triaged_by = actor
    locked.triaged_at = locked.triaged_at or timezone.now()
    if private_note:
        locked.staff_note_private = private_note.strip()
    locked.save()
    return locked


@transaction.atomic
def resolve_report(*, report, actor, resolution_code, dismissed=False, private_note="") -> Report:
    _require_platform_reviewer(actor)
    locked = Report.objects.select_for_update().get(pk=report.pk)
    target = ReportStatus.DISMISSED if dismissed else ReportStatus.RESOLVED
    if locked.status == target:
        return locked
    if locked.status in {ReportStatus.RESOLVED, ReportStatus.DISMISSED}:
        raise ValidationError("Ce signalement possède déjà un résultat final.")
    locked.status = target
    locked.resolution_code = (resolution_code or "").strip()
    locked.resolved_by = actor
    locked.resolved_at = timezone.now()
    if private_note:
        locked.staff_note_private = private_note.strip()
    locked.save()
    return locked


@transaction.atomic
def open_dispute(*, report, actor) -> Dispute:
    _require_platform_reviewer(actor)
    locked_report = Report.objects.select_for_update().select_related("journey", "activity", "space", "reporter").get(pk=report.pk)
    existing = Dispute.objects.select_for_update().filter(report=locked_report).first()
    if existing:
        return existing
    space = locked_report.space or (locked_report.activity.space if locked_report.activity_id else None)
    if space is None:
        raise ValidationError("Le signalement ne fournit pas de partie opérateur explicite.")
    dispute = Dispute(
        report=locked_report,
        journey=locked_report.journey,
        claimant=locked_report.reporter,
        respondent_space=space,
        status=DisputeStatus.OPEN,
    )
    dispute.full_clean()
    dispute.save()
    return dispute


@transaction.atomic
def request_dispute_information(*, dispute, actor) -> Dispute:
    _require_platform_reviewer(actor)
    locked = Dispute.objects.select_for_update().get(pk=dispute.pk)
    if locked.status == DisputeStatus.AWAITING_INFORMATION:
        return locked
    if locked.status in {DisputeStatus.DECIDED, DisputeStatus.CLOSED}:
        raise ValidationError("Ce litige ne peut plus demander d’information.")
    locked.status = DisputeStatus.AWAITING_INFORMATION
    locked.save(update_fields=["status", "updated_at"])
    return locked


@transaction.atomic
def decide_dispute(
    *,
    dispute,
    actor,
    decision_code,
    decision_summary,
    remedy_code=RemedyCode.NONE,
    private_note="",
) -> Dispute:
    _require_platform_reviewer(actor)
    locked = Dispute.objects.select_for_update().get(pk=dispute.pk)
    if locked.status == DisputeStatus.DECIDED and locked.decision_code == decision_code:
        return locked
    if locked.status == DisputeStatus.CLOSED:
        raise ValidationError("Un litige clos ne peut pas recevoir une nouvelle décision.")
    locked.status = DisputeStatus.DECIDED
    locked.decision_code = (decision_code or "").strip()
    locked.decision_summary = (decision_summary or "").strip()
    locked.decision_note_private = (private_note or "").strip()
    locked.remedy_code = remedy_code
    locked.decided_by = actor
    locked.decided_at = timezone.now()
    locked.full_clean()
    locked.save()
    return locked


@transaction.atomic
def close_dispute(*, dispute, actor) -> Dispute:
    _require_platform_reviewer(actor)
    locked = Dispute.objects.select_for_update().get(pk=dispute.pk)
    if locked.status == DisputeStatus.CLOSED:
        return locked
    if locked.status != DisputeStatus.DECIDED:
        raise ValidationError("Une décision est requise avant la clôture du litige.")
    locked.status = DisputeStatus.CLOSED
    locked.closed_at = timezone.now()
    locked.save(update_fields=["status", "closed_at", "updated_at"])
    return locked


@transaction.atomic
def attach_trust_evidence(*, actor, uploaded_file, verification_claim=None, report=None) -> TrustEvidence:
    _require_authenticated(actor)
    if bool(verification_claim) == bool(report):
        raise ValidationError("Une evidence Trust doit viser exactement un dossier.")
    if verification_claim is not None:
        allowed = verification_claim.requested_by_id == actor.pk
        if verification_claim.subject_profile_id:
            allowed = allowed or verification_claim.subject_profile_id == actor.pk
        if verification_claim.subject_space_id:
            allowed = allowed or can_manage_space_trust(actor, verification_claim.subject_space)
        allowed = allowed or can(actor, PermissionCode.PLATFORM_TRUST_REVIEW)
    else:
        allowed = report.reporter_id == actor.pk or can(actor, PermissionCode.PLATFORM_TRUST_REVIEW)
    if not allowed:
        raise PermissionDenied("Accès à l’evidence refusé.")
    evidence = TrustEvidence(
        verification_claim=verification_claim,
        report=report,
        file=uploaded_file,
        uploaded_by=actor,
    )
    evidence.full_clean()
    evidence.save()
    return evidence


def can_access_evidence(*, evidence, actor) -> bool:
    if not _authenticated(actor):
        return False
    if can(actor, PermissionCode.PLATFORM_TRUST_REVIEW):
        return True
    if evidence.verification_claim_id:
        claim = evidence.verification_claim
        if claim.requested_by_id == actor.pk or claim.subject_profile_id == actor.pk:
            return True
        return bool(claim.subject_space_id and can_manage_space_trust(actor, claim.subject_space))
    return evidence.report.reporter_id == actor.pk


def _proof_eligible(journey, proof_type) -> bool:
    if proof_type == ProofType.JOURNEY_COMPLETED:
        return journey.status == JourneyStatus.FULFILLED
    if proof_type in {ProofType.ACCESS_USED, ProofType.PARTICIPATION_CONFIRMED}:
        return journey.accesses.filter(uses__result=AccessUseResult.ACCEPTED).exists()
    if proof_type == ProofType.SERVICE_COMPLETED:
        if journey.workflow != WorkflowKind.SERVICE:
            return False
        if journey.status == JourneyStatus.FULFILLED:
            return True
        try:
            return journey.service_context.current_outcome == "successful"
        except Exception:
            return False
    return False


@transaction.atomic
def issue_proof(*, journey, proof_type, actor=None, is_public=False) -> Proof:
    if actor is not None:
        _require_platform_reviewer(actor)
    if journey.beneficiary_id is None:
        raise ValidationError("Une Proof publique Makolo exige un bénéficiaire Profile.")
    existing = Proof.objects.select_for_update().filter(
        subject_profile_id=journey.beneficiary_id,
        journey=journey,
        proof_type=proof_type,
    ).first()
    if existing:
        return existing
    if not _proof_eligible(journey, proof_type):
        raise ValidationError("Le fait canonique requis pour cette Proof n’est pas établi.")
    proof = Proof(
        subject_profile=journey.beneficiary,
        journey=journey,
        occurrence=journey.occurrence,
        proof_type=proof_type,
        issued_by=actor,
        is_public=is_public,
    )
    proof.full_clean()
    proof.save()
    return proof


@transaction.atomic
def revoke_proof(*, proof, actor, reason) -> Proof:
    _require_platform_reviewer(actor)
    locked = Proof.objects.select_for_update().get(pk=proof.pk)
    if locked.status == ProofStatus.REVOKED:
        return locked
    locked.status = ProofStatus.REVOKED
    locked.revoked_by = actor
    locked.revoked_at = timezone.now()
    locked.revoke_reason = (reason or "").strip()
    locked.save(update_fields=["status", "revoked_by", "revoked_at", "revoke_reason", "updated_at"])
    return locked
