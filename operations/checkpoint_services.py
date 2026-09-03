from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import AccessUseResult
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import CheckpointAssignment, CheckpointObservation, CheckpointStatus, OccurrenceCheckpoint
from .permissions import user_can_manage_activity_operations


_ALLOWED_TRANSITIONS = {
    CheckpointStatus.PLANNED: {CheckpointStatus.OPEN},
    CheckpointStatus.OPEN: {CheckpointStatus.PAUSED, CheckpointStatus.CLOSED},
    CheckpointStatus.PAUSED: {CheckpointStatus.OPEN, CheckpointStatus.CLOSED},
    CheckpointStatus.CLOSED: set(),
}


def _require_manage(actor, checkpoint):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("Authentification requise.")
    if not user_can_manage_activity_operations(actor, checkpoint.occurrence.activity):
        raise PermissionDenied("Vous n’avez pas l’autorité Operations requise pour cette Activity.")


def _event_scope(checkpoint):
    activity = checkpoint.occurrence.activity
    return {"space_id": activity.space_id, "activity_id": activity.pk}


def _emit(checkpoint, event_type, *, source_type="occurrence_checkpoint", source_id=None, payload=None, occurred_at=None, suffix=""):
    body = {
        "checkpoint_id": str(checkpoint.pk),
        "occurrence_id": str(checkpoint.occurrence_id),
    }
    body.update(payload or {})
    emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id or checkpoint.pk,
        idempotency_key=f"checkpoint:{event_type}:{source_id or checkpoint.pk}:{suffix or checkpoint.updated_at.isoformat()}",
        payload=body,
        occurred_at=occurred_at or timezone.now(),
        **_event_scope(checkpoint),
    )


@transaction.atomic
def transition_checkpoint(*, actor, checkpoint, target_status):
    current = (
        OccurrenceCheckpoint.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space")
        .get(pk=checkpoint.pk)
    )
    _require_manage(actor, current)
    if target_status not in _ALLOWED_TRANSITIONS[current.status]:
        raise ValidationError({"status": f"Transition invalide: {current.status} → {target_status}."})
    current.status = target_status
    current.save(update_fields=["status", "updated_at"])
    event_type = {
        CheckpointStatus.OPEN: DomainEventType.CHECKPOINT_OPENED,
        CheckpointStatus.PAUSED: DomainEventType.CHECKPOINT_PAUSED,
        CheckpointStatus.CLOSED: DomainEventType.CHECKPOINT_CLOSED,
    }[target_status]
    _emit(current, event_type)
    return current


def open_checkpoint(*, actor, checkpoint):
    return transition_checkpoint(actor=actor, checkpoint=checkpoint, target_status=CheckpointStatus.OPEN)


def pause_checkpoint(*, actor, checkpoint):
    return transition_checkpoint(actor=actor, checkpoint=checkpoint, target_status=CheckpointStatus.PAUSED)


def resume_checkpoint(*, actor, checkpoint):
    return transition_checkpoint(actor=actor, checkpoint=checkpoint, target_status=CheckpointStatus.OPEN)


def close_checkpoint(*, actor, checkpoint):
    return transition_checkpoint(actor=actor, checkpoint=checkpoint, target_status=CheckpointStatus.CLOSED)


@transaction.atomic
def assign_checkpoint_operator(*, actor, checkpoint, profile):
    current_checkpoint = (
        OccurrenceCheckpoint.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space")
        .get(pk=checkpoint.pk)
    )
    _require_manage(actor, current_checkpoint)
    existing = CheckpointAssignment.objects.select_for_update().filter(
        checkpoint=current_checkpoint, profile=profile, ended_at__isnull=True
    ).first()
    if existing:
        return existing
    assignment = CheckpointAssignment(checkpoint=current_checkpoint, profile=profile, assigned_by=actor)
    try:
        assignment.save()
    except IntegrityError as exc:
        raise ValidationError("Une affectation active existe déjà pour cet opérateur sur ce checkpoint.") from exc
    _emit(
        current_checkpoint,
        DomainEventType.CHECKPOINT_ASSIGNMENT_CHANGED,
        source_type="checkpoint_assignment",
        source_id=assignment.pk,
        payload={"assignment_id": str(assignment.pk), "change": "assigned"},
        occurred_at=assignment.assigned_at,
        suffix="assigned",
    )
    return assignment


@transaction.atomic
def end_checkpoint_assignment(*, actor, assignment):
    current = (
        CheckpointAssignment.objects.select_for_update(of=("self",))
        .select_related("checkpoint", "checkpoint__occurrence", "checkpoint__occurrence__activity", "checkpoint__occurrence__activity__space")
        .get(pk=assignment.pk)
    )
    _require_manage(actor, current.checkpoint)
    if current.ended_at is None:
        current.ended_at = timezone.now()
        current.save(update_fields=["ended_at"])
        _emit(
            current.checkpoint,
            DomainEventType.CHECKPOINT_ASSIGNMENT_CHANGED,
            source_type="checkpoint_assignment",
            source_id=current.pk,
            payload={"assignment_id": str(current.pk), "change": "ended"},
            occurred_at=current.ended_at,
            suffix="ended",
        )
    return current


def _subject_kwargs(*, profile=None, external_beneficiary=None):
    if bool(profile) == bool(external_beneficiary):
        raise ValidationError("L’observation doit viser exactement un bénéficiaire, Profile ou externe.")
    return {"profile": profile, "external_beneficiary": external_beneficiary}


def _validate_access_use(*, checkpoint, access_use, profile=None, external_beneficiary=None):
    if access_use.result != AccessUseResult.ACCEPTED:
        raise ValidationError({"access_use": "Seul un AccessUse accepté peut confirmer un passage de checkpoint."})
    access = access_use.access
    if access.activity_id != checkpoint.occurrence.activity_id:
        raise ValidationError({"access_use": "Cet AccessUse appartient à une autre Activity."})
    if access_use.occurrence_id != checkpoint.occurrence_id:
        raise ValidationError({"access_use": "Cet AccessUse appartient à une autre Occurrence."})
    if profile is not None and access.beneficiary_id != profile.pk:
        raise ValidationError({"access_use": "Le bénéficiaire Profile de l’AccessUse ne correspond pas."})
    if external_beneficiary is not None and access.external_beneficiary_id != external_beneficiary.pk:
        raise ValidationError({"access_use": "Le bénéficiaire externe de l’AccessUse ne correspond pas."})


@transaction.atomic
def observe_checkpoint(
    *,
    actor,
    checkpoint,
    profile=None,
    external_beneficiary=None,
    source="operator",
    client_reference="",
    access_use=None,
):
    subject = _subject_kwargs(profile=profile, external_beneficiary=external_beneficiary)
    current = (
        OccurrenceCheckpoint.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space")
        .get(pk=checkpoint.pk)
    )
    _require_manage(actor, current)
    if not current.active or current.status != CheckpointStatus.OPEN:
        raise ValidationError({"checkpoint": "Le checkpoint doit être actif et ouvert pour enregistrer un passage."})
    if access_use is not None:
        _validate_access_use(checkpoint=current, access_use=access_use, **subject)

    if source and client_reference:
        retry = CheckpointObservation.objects.filter(source=source, client_reference=client_reference).first()
        if retry:
            if retry.checkpoint_id != current.pk:
                raise ValidationError({"client_reference": "Cette référence idempotente est déjà utilisée ailleurs."})
            return retry

    existing = CheckpointObservation.objects.filter(checkpoint=current, **subject).first()
    if existing:
        return existing

    observation = CheckpointObservation(
        checkpoint=current,
        observed_by=actor,
        source=(source or "").strip(),
        client_reference=(client_reference or "").strip(),
        access_use=access_use,
        **subject,
    )
    try:
        observation.save()
    except IntegrityError as exc:
        retry = CheckpointObservation.objects.filter(checkpoint=current, **subject).first()
        if retry:
            return retry
        raise ValidationError("Conflit lors de l’enregistrement du passage.") from exc

    _emit(
        current,
        DomainEventType.CHECKPOINT_OBSERVED,
        source_type="checkpoint_observation",
        source_id=observation.pk,
        payload={
            "observation_id": str(observation.pk),
            "subject_type": "profile" if observation.profile_id else "external_beneficiary",
            "access_use_id": str(observation.access_use_id) if observation.access_use_id else None,
        },
        occurred_at=observation.observed_at,
        suffix="observed",
    )
    return observation
