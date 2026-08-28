from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from authorization.services import has_platform_authority
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import (
    Opportunity,
    OpportunityPublicationStatus,
    OpportunityRequirement,
    OpportunityRevision,
    OpportunitySave,
    OpportunitySource,
    OpportunitySourceCheck,
    OpportunitySourceCheckResult,
    OpportunitySourceStatus,
    OpportunitySubmission,
    OpportunitySubmissionStatus,
    OpportunityZone,
)


def _ensure_curator(actor):
    if not getattr(actor, "is_authenticated", False) or not has_platform_authority(actor):
        raise PermissionDenied("Une autorité plateforme Makolo est requise pour la curation Opportunity.")


def _emit(event_type, *, source_type, source_id, suffix, payload):
    return emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=f"{source_type}:{source_id}:{suffix}"[:255],
        payload=payload,
    )


def canonical_opportunity(opportunity):
    current = opportunity
    visited = set()
    while current.publication_status == OpportunityPublicationStatus.MERGED:
        if current.pk in visited or not current.merged_into_id:
            raise ValidationError("Cycle ou cible invalide dans les merges Opportunity.")
        visited.add(current.pk)
        current = Opportunity.objects.select_related("merged_into").get(pk=current.merged_into_id)
    return current


def _canonical_locked(opportunity_id):
    visited = set()
    current_id = opportunity_id
    while True:
        if current_id in visited:
            raise ValidationError("Cycle détecté dans les merges Opportunity.")
        visited.add(current_id)
        current = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=current_id)
        if current.publication_status != OpportunityPublicationStatus.MERGED:
            return current
        if not current.merged_into_id:
            raise ValidationError("Opportunity fusionnée sans cible canonique.")
        current_id = current.merged_into_id


@transaction.atomic
def create_opportunity(*, actor, kind):
    _ensure_curator(actor)
    opportunity = Opportunity(kind=kind, created_by=actor)
    opportunity.save()
    return opportunity


@transaction.atomic
def create_opportunity_revision(*, opportunity, actor, title, issuer_name, summary="", opens_at=None, deadline_at=None, timezone_name="Africa/Lubumbashi", application_instructions="", remote_allowed=None, change_summary=""):
    _ensure_curator(actor)
    opportunity = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=opportunity.pk)
    if opportunity.publication_status == OpportunityPublicationStatus.MERGED:
        raise ValidationError("Créez les nouvelles révisions sur l’Opportunity canonique.")
    latest = opportunity.revisions.aggregate(value=Max("version"))["value"] or 0
    revision = OpportunityRevision(
        opportunity=opportunity,
        version=latest + 1,
        title=(title or "").strip(),
        summary=summary or "",
        issuer_name=(issuer_name or "").strip(),
        opens_at=opens_at,
        deadline_at=deadline_at,
        timezone=(timezone_name or "").strip(),
        application_instructions=application_instructions or "",
        remote_allowed=remote_allowed,
        change_summary=change_summary or "",
        created_by=actor,
    )
    try:
        revision.save()
    except IntegrityError as exc:
        raise ValidationError("Conflit concurrent lors de la création de la révision Opportunity.") from exc
    return revision


@transaction.atomic
def add_opportunity_zone(*, revision, zone, role, actor):
    _ensure_curator(actor)
    revision = OpportunityRevision.objects.select_for_update(of=("self",)).order_by().get(pk=revision.pk)
    if revision.published_at is not None:
        raise ValidationError("Une révision publiée est immuable.")
    relation = OpportunityZone(revision=revision, zone=zone, role=role)
    relation.save()
    return relation


@transaction.atomic
def add_requirement(*, revision, actor, kind, title, description="", is_mandatory=True, position=0):
    _ensure_curator(actor)
    revision = OpportunityRevision.objects.select_for_update(of=("self",)).order_by().get(pk=revision.pk)
    if revision.published_at is not None:
        raise ValidationError("Une révision publiée est immuable.")
    requirement = OpportunityRequirement(revision=revision, kind=kind, title=(title or "").strip(), description=description or "", is_mandatory=is_mandatory, position=position)
    requirement.save()
    return requirement


@transaction.atomic
def create_opportunity_source(*, opportunity, actor, source_type, source_name, url, external_reference="", is_primary=False, verified=False):
    _ensure_curator(actor)
    opportunity = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=opportunity.pk)
    if opportunity.publication_status == OpportunityPublicationStatus.MERGED:
        raise ValidationError("Ajoutez les sources à l’Opportunity canonique.")
    source = OpportunitySource(
        opportunity=opportunity,
        source_type=source_type,
        source_name=(source_name or "").strip(),
        url=url,
        external_reference=(external_reference or "").strip(),
        is_primary=is_primary,
        verified_at=timezone.now() if verified else None,
        verified_by=actor if verified else None,
    )
    try:
        source.save()
    except IntegrityError as exc:
        raise ValidationError("Une seule source primaire active est autorisée.") from exc
    return source


@transaction.atomic
def publish_opportunity_revision(*, opportunity, revision, actor):
    _ensure_curator(actor)
    opportunity = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=opportunity.pk)
    revision = OpportunityRevision.objects.select_for_update(of=("self",)).order_by().get(pk=revision.pk)
    if revision.opportunity_id != opportunity.pk:
        raise ValidationError("Cette révision appartient à une autre Opportunity.")
    if opportunity.publication_status == OpportunityPublicationStatus.MERGED:
        raise ValidationError("Une Opportunity fusionnée ne peut pas être publiée.")
    if not OpportunitySource.objects.filter(opportunity=opportunity, status=OpportunitySourceStatus.ACTIVE, is_primary=True).exists():
        raise ValidationError("Une Opportunity publique exige une source primaire active.")
    if revision.published_at is not None:
        if opportunity.current_revision_id == revision.pk:
            return revision
        raise ValidationError("Cette révision a déjà été publiée et n’est plus la révision courante.")
    if opportunity.current_revision_id:
        current = OpportunityRevision.objects.get(pk=opportunity.current_revision_id)
        if revision.version <= current.version:
            raise ValidationError("Une nouvelle publication doit avancer la version Opportunity.")
    revision.full_clean()
    now = timezone.now()
    revision.published_at = now
    revision._allow_publication = True
    revision.save(update_fields=["published_at"])
    opportunity.current_revision = revision
    opportunity.publication_status = OpportunityPublicationStatus.PUBLISHED
    opportunity.published_at = opportunity.published_at or now
    opportunity._allow_lifecycle_transition = True
    opportunity.save(update_fields=["current_revision", "publication_status", "published_at", "updated_at"])
    _emit(DomainEventType.OPPORTUNITY_REVISION_PUBLISHED, source_type="opportunity_revision", source_id=revision.pk, suffix=f"published:{revision.version}", payload={"opportunity_id": str(opportunity.pk), "revision_id": str(revision.pk), "version": revision.version})
    return revision


@transaction.atomic
def record_source_check(*, source, result, checked_by=None, fingerprint="", note=""):
    if checked_by is not None:
        _ensure_curator(checked_by)
    source = OpportunitySource.objects.select_for_update(of=("self",)).select_related("opportunity").order_by().get(pk=source.pk)
    checked_at = timezone.now()
    check = OpportunitySourceCheck.objects.create(source=source, result=result, checked_at=checked_at, checked_by=checked_by, fingerprint=(fingerprint or "").strip(), note=note or "")
    status_map = {
        OpportunitySourceCheckResult.UNCHANGED: OpportunitySourceStatus.ACTIVE,
        OpportunitySourceCheckResult.CHANGED: OpportunitySourceStatus.CHANGED,
        OpportunitySourceCheckResult.UNREACHABLE: OpportunitySourceStatus.UNREACHABLE,
        OpportunitySourceCheckResult.REMOVED: OpportunitySourceStatus.REMOVED,
    }
    source.status = status_map[result]
    source.last_checked_at = checked_at
    source._allow_status_transition = True
    source.save(update_fields=["status", "last_checked_at", "updated_at"])
    if result == OpportunitySourceCheckResult.CHANGED:
        _emit(DomainEventType.OPPORTUNITY_SOURCE_CHANGED, source_type="opportunity_source_check", source_id=check.pk, suffix="changed", payload={"opportunity_id": str(source.opportunity_id), "source_id": str(source.pk), "check_id": str(check.pk)})
    return check


@transaction.atomic
def withdraw_opportunity(*, opportunity, actor):
    _ensure_curator(actor)
    opportunity = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=opportunity.pk)
    if opportunity.publication_status == OpportunityPublicationStatus.WITHDRAWN:
        return opportunity
    if opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED:
        raise ValidationError("Seule une Opportunity publiée peut être retirée.")
    opportunity.publication_status = OpportunityPublicationStatus.WITHDRAWN
    opportunity._allow_lifecycle_transition = True
    opportunity.save(update_fields=["publication_status", "updated_at"])
    _emit(DomainEventType.OPPORTUNITY_WITHDRAWN, source_type="opportunity", source_id=opportunity.pk, suffix="withdrawn", payload={"opportunity_id": str(opportunity.pk), "revision_id": str(opportunity.current_revision_id or "")})
    return opportunity


@transaction.atomic
def archive_opportunity(*, opportunity, actor):
    _ensure_curator(actor)
    opportunity = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=opportunity.pk)
    if opportunity.publication_status == OpportunityPublicationStatus.ARCHIVED:
        return opportunity
    if opportunity.publication_status == OpportunityPublicationStatus.MERGED:
        raise ValidationError("Une Opportunity fusionnée conserve son lifecycle merged.")
    opportunity.publication_status = OpportunityPublicationStatus.ARCHIVED
    opportunity._allow_lifecycle_transition = True
    opportunity.save(update_fields=["publication_status", "updated_at"])
    return opportunity


@transaction.atomic
def save_opportunity(*, profile, opportunity):
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Authentification requise pour sauvegarder une Opportunity.")
    canonical = canonical_opportunity(opportunity)
    saved, _ = OpportunitySave.objects.get_or_create(profile=profile, opportunity=canonical)
    return saved


@transaction.atomic
def unsave_opportunity(*, profile, opportunity):
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    canonical = canonical_opportunity(opportunity)
    deleted, _ = OpportunitySave.objects.filter(profile=profile, opportunity=canonical).delete()
    return bool(deleted)


@transaction.atomic
def submit_opportunity(*, submitted_by, url, title="", comment=""):
    if not getattr(submitted_by, "is_authenticated", False):
        raise PermissionDenied("Authentification requise pour proposer une Opportunity.")
    return OpportunitySubmission.objects.create(submitted_by=submitted_by, url=url, title=(title or "").strip(), comment=comment or "")


@transaction.atomic
def start_submission_review(*, submission, actor):
    _ensure_curator(actor)
    submission = OpportunitySubmission.objects.select_for_update(of=("self",)).order_by().get(pk=submission.pk)
    if submission.status == OpportunitySubmissionStatus.UNDER_REVIEW:
        return submission
    if submission.status != OpportunitySubmissionStatus.PENDING:
        raise ValidationError("Seule une submission en attente peut entrer en revue.")
    submission.status = OpportunitySubmissionStatus.UNDER_REVIEW
    submission.reviewed_by = actor
    submission._allow_status_transition = True
    submission.save(update_fields=["status", "reviewed_by", "updated_at"])
    return submission


@transaction.atomic
def decide_opportunity_submission(*, submission, actor, decision, resolved_opportunity=None, review_note=""):
    _ensure_curator(actor)
    allowed = {OpportunitySubmissionStatus.ACCEPTED, OpportunitySubmissionStatus.REJECTED, OpportunitySubmissionStatus.DUPLICATE}
    if decision not in allowed:
        raise ValidationError("Décision OpportunitySubmission invalide.")
    submission = OpportunitySubmission.objects.select_for_update(of=("self",)).order_by().get(pk=submission.pk)
    if submission.status != OpportunitySubmissionStatus.UNDER_REVIEW:
        raise ValidationError("La submission doit être en revue avant décision.")
    if decision in {OpportunitySubmissionStatus.ACCEPTED, OpportunitySubmissionStatus.DUPLICATE}:
        if resolved_opportunity is None:
            raise ValidationError("Cette décision doit référencer une Opportunity.")
        resolved_opportunity = canonical_opportunity(resolved_opportunity)
    elif resolved_opportunity is not None:
        raise ValidationError("Une submission rejetée ne référence pas d’Opportunity résolue.")
    submission.status = decision
    submission.reviewed_by = actor
    submission.reviewed_at = timezone.now()
    submission.review_note = review_note or ""
    submission.resolved_opportunity = resolved_opportunity
    submission._allow_status_transition = True
    submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "resolved_opportunity", "updated_at"])
    return submission


@transaction.atomic
def merge_opportunities(*, canonical, duplicate, actor):
    _ensure_curator(actor)
    if canonical.pk == duplicate.pk:
        raise ValidationError("Une Opportunity ne peut pas être fusionnée vers elle-même.")
    canonical = _canonical_locked(canonical.pk)
    duplicate = Opportunity.objects.select_for_update(of=("self",)).order_by().get(pk=duplicate.pk)
    if duplicate.pk == canonical.pk:
        raise ValidationError("La cible canonique et le doublon se résolvent vers la même Opportunity.")
    if duplicate.publication_status == OpportunityPublicationStatus.MERGED:
        existing = _canonical_locked(duplicate.pk)
        if existing.pk == canonical.pk:
            return duplicate
        raise ValidationError("Cette Opportunity est déjà fusionnée vers une autre cible.")
    # Refuse the only cycle that can arise when canonical ultimately resolves through duplicate.
    probe = canonical
    visited = set()
    while probe.publication_status == OpportunityPublicationStatus.MERGED:
        if probe.pk in visited or probe.merged_into_id == duplicate.pk:
            raise ValidationError("Ce merge créerait un cycle.")
        visited.add(probe.pk)
        probe = _canonical_locked(probe.merged_into_id)
    for saved in list(OpportunitySave.objects.select_for_update().filter(opportunity=duplicate).order_by("pk")):
        OpportunitySave.objects.get_or_create(profile_id=saved.profile_id, opportunity=canonical)
        saved.delete()
    duplicate.publication_status = OpportunityPublicationStatus.MERGED
    duplicate.merged_into = canonical
    duplicate._allow_lifecycle_transition = True
    duplicate.save(update_fields=["publication_status", "merged_into", "updated_at"])
    _emit(DomainEventType.OPPORTUNITY_MERGED, source_type="opportunity", source_id=duplicate.pk, suffix=f"merged:{canonical.pk}", payload={"duplicate_opportunity_id": str(duplicate.pk), "canonical_opportunity_id": str(canonical.pk)})
    return duplicate
