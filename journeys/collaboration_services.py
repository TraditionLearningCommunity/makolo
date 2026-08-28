from __future__ import annotations

import hashlib
import io
import zipfile

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .collaboration_models import (
    JourneyArtifact,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactSensitivity,
    JourneyArtifactStatus,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyBlocker,
    JourneyBlockerCategory,
    JourneyBlockerSeverity,
    JourneyBlockerStatus,
    JourneyNote,
    JourneyNoteVisibility,
    JourneyStep,
    JourneyStepAssignment,
    JourneyStepDependency,
    JourneyStepKind,
    JourneyStepStatus,
    TERMINAL_STEP_STATUSES,
)


SATISFIED_DEPENDENCY_STATUSES = {JourneyStepStatus.COMPLETED, JourneyStepStatus.SKIPPED}
CASE_WRITE_PERMISSION = PermissionCode.ACTIVITY_MANAGE
CASE_READ_PERMISSION = PermissionCode.ACTIVITY_VIEW


def _actor_id(actor):
    return getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None


def _event_scope(journey):
    return getattr(journey.activity, "space_id", None), journey.activity_id


def _emit_case_event(*, event_type, source_type, source_id, journey, suffix, payload=None):
    space_id, activity_id = _event_scope(journey)
    base_payload = {"journey_id": str(journey.pk), "activity_id": str(activity_id)}
    base_payload.update(payload or {})
    return emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=f"{source_type}:{source_id}:{suffix}"[:255],
        space_id=space_id,
        activity_id=activity_id,
        payload=base_payload,
    )


def _active_assignment_exists(profile, journey):
    profile_id = _actor_id(profile)
    if not profile_id:
        return False
    return JourneyAssignment.objects.filter(journey=journey, profile_id=profile_id, status=JourneyAssignmentStatus.ACTIVE).exists()


def is_beneficiary(actor, journey):
    return bool(_actor_id(actor) and journey.beneficiary_id == _actor_id(actor))


def can_access_case(actor, journey, *, write=False, restricted=False):
    if is_beneficiary(actor, journey):
        return not write
    permission = CASE_WRITE_PERMISSION if (write or restricted) else CASE_READ_PERMISSION
    return _active_assignment_exists(actor, journey) and can(actor, permission, activity=journey.activity)


def ensure_case_access(actor, journey, *, write=False, restricted=False):
    if not can_access_case(actor, journey, write=write, restricted=restricted):
        raise PermissionDenied("Accès refusé à ce dossier Journey.")


def ensure_case_manager(actor, journey):
    if not getattr(actor, "is_authenticated", False) or not can(actor, CASE_WRITE_PERMISSION, activity=journey.activity):
        raise PermissionDenied("Une autorité Activity de gestion est requise.")


def _lock_step(step):
    return JourneyStep.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "occurrence").order_by().get(pk=step.pk)


def _dependencies_satisfied(step):
    return not JourneyStepDependency.objects.filter(step=step).exclude(depends_on__status__in=SATISFIED_DEPENDENCY_STATUSES).exists()


def _has_active_blockers(step):
    return JourneyBlocker.objects.filter(step=step, status=JourneyBlockerStatus.ACTIVE).exists()


def _save_step_status(step, *, status, actor=None, reason="", event_type=None):
    previous = step.status
    if previous == status:
        return step
    now = timezone.now()
    step.status = status
    step.status_changed_by = actor if _actor_id(actor) else None
    step.status_reason = (reason or "")[:500]
    if status == JourneyStepStatus.IN_PROGRESS and step.started_at is None:
        step.started_at = now
    elif status == JourneyStepStatus.COMPLETED and step.completed_at is None:
        step.completed_at = now
    elif status == JourneyStepStatus.SKIPPED and step.skipped_at is None:
        step.skipped_at = now
    elif status == JourneyStepStatus.CANCELLED and step.cancelled_at is None:
        step.cancelled_at = now
    step._allow_status_transition = True
    step.save()
    if event_type:
        _emit_case_event(
            event_type=event_type,
            source_type="journey_step",
            source_id=step.pk,
            journey=step.journey,
            suffix=f"{status}:{step.updated_at.isoformat()}",
            payload={"step_id": str(step.pk), "previous_status": previous, "status": status, "kind": step.kind},
        )
    return step


def _assert_step_completion_preconditions(step):
    if _has_active_blockers(step):
        raise ValidationError("Une étape bloquée ne peut pas être terminée.")
    if not _dependencies_satisfied(step):
        raise ValidationError("Toutes les dépendances de cette étape ne sont pas satisfaites.")
    if step.kind == JourneyStepKind.DOCUMENT and step.is_required:
        if not JourneyArtifact.objects.filter(step=step, status=JourneyArtifactStatus.ACCEPTED).exists():
            raise ValidationError("Une étape document requise exige un Artifact accepté.")
    if step.kind == JourneyStepKind.REVIEW and step.is_required:
        if not JourneyArtifactReview.objects.filter(artifact__step=step, status=JourneyArtifactReviewStatus.APPROVED).exists():
            raise ValidationError("Une étape de revue requise exige une revue approuvée.")


@transaction.atomic
def create_step(*, journey, title, kind=JourneyStepKind.ACTION, description="", position=0, is_required=True, due_at=None, occurrence=None, origin="manual", created_by=None):
    ensure_case_access(created_by, journey, write=True) if created_by is not None else None
    step = JourneyStep(journey=journey, kind=kind, title=(title or "").strip(), description=description or "", position=position, is_required=is_required, due_at=due_at, occurrence=occurrence, origin=origin, created_by=created_by if _actor_id(created_by) else None)
    step.save()
    return step


@transaction.atomic
def mark_ready(*, step, actor=None, reason="dependencies_satisfied"):
    step = _lock_step(step)
    if step.status == JourneyStepStatus.READY:
        return step
    if step.status != JourneyStepStatus.PENDING:
        raise ValidationError("Seule une étape en attente peut devenir prête.")
    if _has_active_blockers(step) or not _dependencies_satisfied(step):
        raise ValidationError("Cette étape n’est pas encore prête.")
    return _save_step_status(step, status=JourneyStepStatus.READY, actor=actor, reason=reason, event_type=DomainEventType.JOURNEY_STEP_READY)


@transaction.atomic
def start_step(*, step, actor, reason="started"):
    step = _lock_step(step)
    ensure_case_access(actor, step.journey, write=True)
    if step.status == JourneyStepStatus.IN_PROGRESS:
        return step
    if step.status != JourneyStepStatus.READY:
        raise ValidationError("Seule une étape prête peut démarrer.")
    if _has_active_blockers(step) or not _dependencies_satisfied(step):
        raise ValidationError("Cette étape ne peut pas démarrer maintenant.")
    return _save_step_status(step, status=JourneyStepStatus.IN_PROGRESS, actor=actor, reason=reason, event_type=DomainEventType.JOURNEY_STEP_STARTED)


@transaction.atomic
def complete_step(*, step, actor, reason="completed"):
    step = _lock_step(step)
    ensure_case_access(actor, step.journey, write=True)
    if step.status == JourneyStepStatus.COMPLETED:
        return step
    if step.status != JourneyStepStatus.IN_PROGRESS:
        raise ValidationError("Seule une étape en cours peut être terminée.")
    _assert_step_completion_preconditions(step)
    step = _save_step_status(step, status=JourneyStepStatus.COMPLETED, actor=actor, reason=reason, event_type=DomainEventType.JOURNEY_STEP_COMPLETED)
    for dependant in JourneyStep.objects.select_for_update().filter(dependencies__depends_on=step, status=JourneyStepStatus.PENDING).order_by("position", "id"):
        if not _has_active_blockers(dependant) and _dependencies_satisfied(dependant):
            _save_step_status(dependant, status=JourneyStepStatus.READY, actor=actor, reason="dependencies_satisfied", event_type=DomainEventType.JOURNEY_STEP_READY)
    return step


@transaction.atomic
def recalculate_after_unblock(*, step, actor=None):
    step = _lock_step(step)
    if _has_active_blockers(step):
        if step.status in {JourneyStepStatus.READY, JourneyStepStatus.IN_PROGRESS}:
            return _save_step_status(step, status=JourneyStepStatus.BLOCKED, actor=actor, reason="active_blocker", event_type=DomainEventType.JOURNEY_STEP_BLOCKED)
        return step
    if step.status == JourneyStepStatus.BLOCKED:
        if not _dependencies_satisfied(step):
            return step
        target = JourneyStepStatus.IN_PROGRESS if step.started_at else JourneyStepStatus.READY
        event_type = DomainEventType.JOURNEY_STEP_STARTED if target == JourneyStepStatus.IN_PROGRESS else DomainEventType.JOURNEY_STEP_READY
        return _save_step_status(step, status=target, actor=actor, reason="blockers_cleared", event_type=event_type)
    if step.status == JourneyStepStatus.PENDING and _dependencies_satisfied(step):
        return _save_step_status(step, status=JourneyStepStatus.READY, actor=actor, reason="dependencies_satisfied", event_type=DomainEventType.JOURNEY_STEP_READY)
    return step


@transaction.atomic
def skip_step(*, step, actor, reason, allow_required=False):
    step = _lock_step(step)
    ensure_case_access(actor, step.journey, write=True)
    if step.status == JourneyStepStatus.SKIPPED:
        return step
    if step.status in TERMINAL_STEP_STATUSES:
        raise ValidationError("Cette étape est déjà terminale.")
    if step.is_required and not allow_required:
        raise ValidationError("Une étape obligatoire exige une décision explicite pour être ignorée.")
    if not (reason or "").strip():
        raise ValidationError("Une raison est obligatoire pour ignorer une étape.")
    step = _save_step_status(step, status=JourneyStepStatus.SKIPPED, actor=actor, reason=reason)
    for dependant in JourneyStep.objects.select_for_update().filter(dependencies__depends_on=step, status=JourneyStepStatus.PENDING):
        if not _has_active_blockers(dependant) and _dependencies_satisfied(dependant):
            _save_step_status(dependant, status=JourneyStepStatus.READY, actor=actor, reason="dependencies_satisfied", event_type=DomainEventType.JOURNEY_STEP_READY)
    return step


@transaction.atomic
def cancel_step(*, step, actor, reason):
    step = _lock_step(step)
    ensure_case_access(actor, step.journey, write=True)
    if step.status == JourneyStepStatus.CANCELLED:
        return step
    if step.status in TERMINAL_STEP_STATUSES:
        raise ValidationError("Cette étape est déjà terminale.")
    if not (reason or "").strip():
        raise ValidationError("Une raison est obligatoire pour annuler une étape.")
    return _save_step_status(step, status=JourneyStepStatus.CANCELLED, actor=actor, reason=reason)


def _dependency_would_cycle(*, step, depends_on):
    frontier = {depends_on.pk}
    visited = set()
    while frontier:
        if step.pk in frontier:
            return True
        visited.update(frontier)
        frontier = set(JourneyStepDependency.objects.filter(step_id__in=frontier).exclude(depends_on_id__in=visited).values_list("depends_on_id", flat=True))
    return False


@transaction.atomic
def add_step_dependency(*, step, depends_on, actor=None):
    step = _lock_step(step)
    depends_on = _lock_step(depends_on)
    if step.journey_id != depends_on.journey_id:
        raise ValidationError("Une dépendance JourneyStep ne peut pas traverser deux Journeys.")
    if step.pk == depends_on.pk:
        raise ValidationError("Une étape ne peut pas dépendre d’elle-même.")
    if JourneyStepDependency.objects.filter(step=step, depends_on=depends_on).exists():
        raise ValidationError("Cette dépendance existe déjà.")
    if _dependency_would_cycle(step=step, depends_on=depends_on):
        raise ValidationError("Cette dépendance créerait un cycle.")
    dependency = JourneyStepDependency(step=step, depends_on=depends_on)
    dependency.save()
    if step.status == JourneyStepStatus.READY and not _dependencies_satisfied(step):
        _save_step_status(step, status=JourneyStepStatus.PENDING, actor=actor, reason="dependency_added")
    return dependency


@transaction.atomic
def create_blocker(*, journey, title, actor=None, step=None, category=JourneyBlockerCategory.OTHER, severity=JourneyBlockerSeverity.MEDIUM, description="", responsible_profile=None, due_at=None):
    ensure_case_access(actor, journey, write=True) if actor is not None else None
    if step is not None:
        step = _lock_step(step)
        if step.journey_id != journey.pk:
            raise ValidationError("La Step et le blocker doivent appartenir à la même Journey.")
    blocker = JourneyBlocker(journey=journey, step=step, category=category, severity=severity, title=(title or "").strip(), description=description or "", responsible_profile=responsible_profile, detected_by=actor if _actor_id(actor) else None, due_at=due_at)
    blocker.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_BLOCKER_CREATED, source_type="journey_blocker", source_id=blocker.pk, journey=journey, suffix="created", payload={"blocker_id": str(blocker.pk), "step_id": str(step.pk) if step else None, "category": blocker.category, "severity": blocker.severity, "status": blocker.status})
    if step and step.status in {JourneyStepStatus.READY, JourneyStepStatus.IN_PROGRESS}:
        _save_step_status(step, status=JourneyStepStatus.BLOCKED, actor=actor, reason="blocker_created", event_type=DomainEventType.JOURNEY_STEP_BLOCKED)
    return blocker


@transaction.atomic
def resolve_blocker(*, blocker, actor, resolution_note="", waive=False):
    blocker = JourneyBlocker.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "step").order_by().get(pk=blocker.pk)
    ensure_case_access(actor, blocker.journey, write=True)
    if blocker.status != JourneyBlockerStatus.ACTIVE:
        return blocker
    blocker.status = JourneyBlockerStatus.WAIVED if waive else JourneyBlockerStatus.RESOLVED
    blocker.resolved_by = actor
    blocker.resolved_at = timezone.now()
    blocker.resolution_note = (resolution_note or "").strip()
    blocker._allow_status_transition = True
    blocker.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_BLOCKER_RESOLVED, source_type="journey_blocker", source_id=blocker.pk, journey=blocker.journey, suffix=blocker.status, payload={"blocker_id": str(blocker.pk), "step_id": str(blocker.step_id) if blocker.step_id else None, "status": blocker.status})
    if blocker.step_id:
        recalculate_after_unblock(step=blocker.step, actor=actor)
    return blocker


@transaction.atomic
def assign_journey(*, journey, profile, responsibility, assigned_by, is_primary=False, replace_primary=False):
    ensure_case_manager(assigned_by, journey)
    from .models import Journey
    Journey.objects.select_for_update(of=("self",)).order_by().get(pk=journey.pk)
    if responsibility == JourneyAssignmentResponsibility.LEAD and is_primary:
        current = JourneyAssignment.objects.select_for_update().filter(journey=journey, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, status=JourneyAssignmentStatus.ACTIVE).order_by().first()
        if current and current.profile_id == profile.pk:
            return current
        if current and not replace_primary:
            raise ValidationError("Cette Journey possède déjà un lead primaire actif.")
        if current:
            current.status = JourneyAssignmentStatus.ENDED
            current.ended_at = timezone.now()
            current._allow_status_transition = True
            current.save()
            _emit_case_event(event_type=DomainEventType.JOURNEY_ASSIGNMENT_ENDED, source_type="journey_assignment", source_id=current.pk, journey=journey, suffix="ended", payload={"assignment_id": str(current.pk), "responsibility": current.responsibility})
    existing = JourneyAssignment.objects.filter(journey=journey, profile=profile, responsibility=responsibility, status=JourneyAssignmentStatus.ACTIVE).first()
    if existing:
        return existing
    assignment = JourneyAssignment(journey=journey, profile=profile, responsibility=responsibility, is_primary=is_primary, assigned_by=assigned_by)
    try:
        assignment.save()
    except IntegrityError as exc:
        raise ValidationError("Conflit concurrent lors de l’affectation Journey.") from exc
    _emit_case_event(event_type=DomainEventType.JOURNEY_ASSIGNMENT_CREATED, source_type="journey_assignment", source_id=assignment.pk, journey=journey, suffix="created", payload={"assignment_id": str(assignment.pk), "profile_id": str(profile.pk), "responsibility": responsibility, "is_primary": bool(is_primary)})
    return assignment


@transaction.atomic
def end_journey_assignment(*, assignment, actor, cancelled=False):
    assignment = JourneyAssignment.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity").order_by().get(pk=assignment.pk)
    ensure_case_manager(actor, assignment.journey)
    if assignment.status != JourneyAssignmentStatus.ACTIVE:
        return assignment
    assignment.status = JourneyAssignmentStatus.CANCELLED if cancelled else JourneyAssignmentStatus.ENDED
    assignment.ended_at = timezone.now()
    assignment._allow_status_transition = True
    assignment.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_ASSIGNMENT_ENDED, source_type="journey_assignment", source_id=assignment.pk, journey=assignment.journey, suffix=assignment.status, payload={"assignment_id": str(assignment.pk), "responsibility": assignment.responsibility, "status": assignment.status})
    return assignment


@transaction.atomic
def assign_step(*, step, profile, responsibility, assigned_by):
    step = _lock_step(step)
    ensure_case_access(assigned_by, step.journey, write=True)
    if not JourneyAssignment.objects.filter(journey=step.journey, profile=profile, status=JourneyAssignmentStatus.ACTIVE).exists():
        raise ValidationError("Une affectation de Step exige d’abord une JourneyAssignment active.")
    assignment, _ = JourneyStepAssignment.objects.get_or_create(step=step, profile=profile, responsibility=responsibility, status=JourneyAssignmentStatus.ACTIVE, defaults={"assigned_by": assigned_by})
    return assignment


SAFE_MIME_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword", "text/plain", "image/jpeg", "image/png"}


def _validate_file_signature(data, mime_type):
    if mime_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if mime_type == "application/msword":
        return data.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if not data.startswith(b"PK"):
            return False
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                return "[Content_Types].xml" in names and "word/document.xml" in names
        except zipfile.BadZipFile:
            return False
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "text/plain":
        try:
            data.decode("utf-8")
            return b"\x00" not in data
        except UnicodeDecodeError:
            return False
    return False


def validate_artifact_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("Un fichier est obligatoire.")
    max_size = int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024))
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0:
        raise ValidationError("Le fichier est vide.")
    if size > max_size:
        raise ValidationError("Le fichier dépasse la taille maximale autorisée.")
    declared = (getattr(uploaded_file, "content_type", "") or "").split(";", 1)[0].strip().lower()
    if declared not in SAFE_MIME_TYPES:
        raise ValidationError("Type MIME de fichier non pris en charge.")
    uploaded_file.seek(0)
    data = uploaded_file.read(max_size + 1)
    uploaded_file.seek(0)
    if len(data) != size or len(data) > max_size:
        raise ValidationError("La taille réelle du fichier ne correspond pas à la taille annoncée.")
    if not _validate_file_signature(data, declared):
        raise ValidationError("Le contenu du fichier ne correspond pas au type MIME annoncé.")
    return data, declared, hashlib.sha256(data).hexdigest()


@transaction.atomic
def create_artifact(*, journey, uploaded_file, uploaded_by, kind, title, step=None, sensitivity=JourneyArtifactSensitivity.NORMAL, status=JourneyArtifactStatus.DRAFT):
    if not is_beneficiary(uploaded_by, journey):
        ensure_case_access(uploaded_by, journey, write=True, restricted=sensitivity == JourneyArtifactSensitivity.RESTRICTED)
    if step is not None and step.journey_id != journey.pk:
        raise ValidationError("La Step et l’Artifact doivent appartenir à la même Journey.")
    data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
    artifact = JourneyArtifact(journey=journey, step=step, kind=kind, title=(title or "").strip(), status=status, sensitivity=sensitivity, version=1, uploaded_by=uploaded_by, size=len(data), mime_type=mime_type, content_hash=content_hash)
    artifact.file.save("artifact.bin", ContentFile(data), save=False)
    try:
        artifact.save()
    except Exception:
        if artifact.file.name:
            artifact.file.storage.delete(artifact.file.name)
        raise
    _emit_case_event(event_type=DomainEventType.JOURNEY_ARTIFACT_CREATED, source_type="journey_artifact", source_id=artifact.pk, journey=journey, suffix="created", payload={"artifact_id": str(artifact.pk), "step_id": str(step.pk) if step else None, "kind": kind, "status": status, "sensitivity": sensitivity, "version": 1})
    return artifact


@transaction.atomic
def create_artifact_version(*, artifact, uploaded_file, uploaded_by, sensitivity=None):
    previous = JourneyArtifact.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "step").order_by().get(pk=artifact.pk)
    if not is_beneficiary(uploaded_by, previous.journey):
        ensure_case_access(uploaded_by, previous.journey, write=True, restricted=(sensitivity or previous.sensitivity) == JourneyArtifactSensitivity.RESTRICTED)
    if JourneyArtifact.objects.filter(supersedes=previous).exists():
        raise ValidationError("Cet Artifact a déjà une version suivante.")
    data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
    successor = JourneyArtifact(journey=previous.journey, step=previous.step, kind=previous.kind, title=previous.title, status=JourneyArtifactStatus.DRAFT, sensitivity=sensitivity or previous.sensitivity, supersedes=previous, version=previous.version + 1, uploaded_by=uploaded_by, size=len(data), mime_type=mime_type, content_hash=content_hash)
    successor.file.save("artifact.bin", ContentFile(data), save=False)
    try:
        successor.save()
    except Exception:
        if successor.file.name:
            successor.file.storage.delete(successor.file.name)
        raise
    previous.status = JourneyArtifactStatus.SUPERSEDED
    previous._allow_status_transition = True
    previous.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_ARTIFACT_CREATED, source_type="journey_artifact", source_id=successor.pk, journey=successor.journey, suffix="created", payload={"artifact_id": str(successor.pk), "supersedes_id": str(previous.pk), "kind": successor.kind, "status": successor.status, "sensitivity": successor.sensitivity, "version": successor.version})
    return successor


@transaction.atomic
def request_artifact_review(*, artifact, reviewer, requested_by, comment=""):
    artifact = JourneyArtifact.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity").order_by().get(pk=artifact.pk)
    ensure_case_access(requested_by, artifact.journey, write=True)
    if not JourneyAssignment.objects.filter(journey=artifact.journey, profile=reviewer, status=JourneyAssignmentStatus.ACTIVE).exists() or not can(reviewer, CASE_WRITE_PERMISSION, activity=artifact.journey.activity):
        raise ValidationError("Le reviewer doit avoir autorité Activity et une JourneyAssignment active.")
    if artifact.status == JourneyArtifactStatus.SUPERSEDED:
        raise ValidationError("Une version remplacée ne peut pas entrer en revue.")
    review = JourneyArtifactReview.objects.create(artifact=artifact, reviewer=reviewer, requested_by=requested_by, comment=(comment or "").strip())
    artifact.status = JourneyArtifactStatus.IN_REVIEW
    artifact._allow_status_transition = True
    artifact.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED, source_type="journey_artifact_review", source_id=review.pk, journey=artifact.journey, suffix="requested", payload={"review_id": str(review.pk), "artifact_id": str(artifact.pk), "status": review.status})
    return review


def _ensure_reviewer(actor, review):
    if review.reviewer_id != _actor_id(actor):
        raise PermissionDenied("Seul le reviewer désigné peut décider cette revue.")
    ensure_case_access(actor, review.artifact.journey, write=True)


@transaction.atomic
def start_artifact_review(*, review, actor):
    review = JourneyArtifactReview.objects.select_for_update(of=("self",)).select_related("artifact", "artifact__journey", "artifact__journey__activity").order_by().get(pk=review.pk)
    _ensure_reviewer(actor, review)
    if review.status == JourneyArtifactReviewStatus.IN_PROGRESS:
        return review
    if review.status != JourneyArtifactReviewStatus.REQUESTED:
        raise ValidationError("Cette revue ne peut pas être démarrée.")
    review.status = JourneyArtifactReviewStatus.IN_PROGRESS
    review.started_at = review.started_at or timezone.now()
    review._allow_status_transition = True
    review.save()
    return review


@transaction.atomic
def decide_artifact_review(*, review, actor, decision, comment=""):
    if decision not in {JourneyArtifactReviewStatus.APPROVED, JourneyArtifactReviewStatus.CHANGES_REQUESTED}:
        raise ValidationError("Décision de revue invalide.")
    review = JourneyArtifactReview.objects.select_for_update(of=("self",)).select_related("artifact", "artifact__journey", "artifact__journey__activity").order_by().get(pk=review.pk)
    artifact = JourneyArtifact.objects.select_for_update(of=("self",)).order_by().get(pk=review.artifact_id)
    review.artifact = artifact
    _ensure_reviewer(actor, review)
    if review.status not in {JourneyArtifactReviewStatus.REQUESTED, JourneyArtifactReviewStatus.IN_PROGRESS}:
        raise ValidationError("Cette revue a déjà été décidée.")
    review.status = decision
    review.comment = (comment or "").strip()
    review.started_at = review.started_at or timezone.now()
    review.decided_at = timezone.now()
    review._allow_status_transition = True
    review.save()
    artifact.status = JourneyArtifactStatus.ACCEPTED if decision == JourneyArtifactReviewStatus.APPROVED else JourneyArtifactStatus.REJECTED
    artifact._allow_status_transition = True
    artifact.save()
    _emit_case_event(event_type=DomainEventType.JOURNEY_ARTIFACT_REVIEW_COMPLETED, source_type="journey_artifact_review", source_id=review.pk, journey=artifact.journey, suffix=decision, payload={"review_id": str(review.pk), "artifact_id": str(artifact.pk), "status": decision})
    return review


@transaction.atomic
def cancel_artifact_review(*, review, actor, comment=""):
    review = JourneyArtifactReview.objects.select_for_update(of=("self",)).select_related("artifact", "artifact__journey", "artifact__journey__activity").order_by().get(pk=review.pk)
    is_requester = review.requested_by_id == _actor_id(actor)
    if not is_requester:
        ensure_case_access(actor, review.artifact.journey, write=True)
    if review.status in {JourneyArtifactReviewStatus.APPROVED, JourneyArtifactReviewStatus.CHANGES_REQUESTED}:
        raise ValidationError("Une revue décidée ne peut plus être annulée.")
    if review.status == JourneyArtifactReviewStatus.CANCELLED:
        return review
    review.status = JourneyArtifactReviewStatus.CANCELLED
    review.comment = (comment or "").strip()
    review.decided_at = timezone.now()
    review._allow_status_transition = True
    review.save()
    return review


@transaction.atomic
def create_note(*, journey, author, body, visibility, step=None):
    if not is_beneficiary(author, journey):
        ensure_case_access(author, journey, write=True)
    if is_beneficiary(author, journey) and visibility != JourneyNoteVisibility.BENEFICIARY_VISIBLE:
        raise PermissionDenied("Le bénéficiaire ne peut pas créer de note interne.")
    if step is not None and step.journey_id != journey.pk:
        raise ValidationError("La Step et la note doivent appartenir à la même Journey.")
    note = JourneyNote(journey=journey, step=step, author=author, body=body, visibility=visibility)
    note.save()
    return note


def notes_for_actor(*, actor, journey):
    if is_beneficiary(actor, journey):
        return JourneyNote.objects.filter(journey=journey, visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE).select_related("author", "step")
    ensure_case_access(actor, journey, write=False)
    return JourneyNote.objects.filter(journey=journey).select_related("author", "step")


def artifacts_for_actor(*, actor, journey):
    ensure_case_access(actor, journey, write=False)
    queryset = JourneyArtifact.objects.filter(journey=journey).select_related("step", "uploaded_by")
    if is_beneficiary(actor, journey):
        return queryset
    if not can(actor, CASE_WRITE_PERMISSION, activity=journey.activity):
        return queryset.exclude(sensitivity=JourneyArtifactSensitivity.RESTRICTED)
    return queryset


def artifact_for_download(*, actor, artifact_id):
    artifact = JourneyArtifact.objects.select_related("journey", "journey__activity", "step", "uploaded_by").filter(pk=artifact_id).first()
    if artifact is None:
        raise PermissionDenied("Artifact inaccessible.")
    ensure_case_access(actor, artifact.journey, write=False, restricted=artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED)
    return artifact