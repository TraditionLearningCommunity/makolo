from dataclasses import dataclass

from .models import CheckpointAssignment, CheckpointObservation, CheckpointStatus, OccurrenceCheckpoint


@dataclass(frozen=True)
class NextCheckpointResult:
    checkpoint: OccurrenceCheckpoint | None
    blocked_reason: str = ""


def ordered_checkpoints(*, occurrence):
    return OccurrenceCheckpoint.objects.filter(occurrence=occurrence, active=True).order_by("position", "label", "id")


def observations_for_beneficiary(*, occurrence, profile=None, external_beneficiary=None):
    if bool(profile) == bool(external_beneficiary):
        raise ValueError("Exactly one beneficiary is required.")
    filters = {"profile": profile} if profile is not None else {"external_beneficiary": external_beneficiary}
    return CheckpointObservation.objects.filter(checkpoint__occurrence=occurrence, **filters).select_related(
        "checkpoint", "observed_by", "access_use"
    )


def next_checkpoint(*, occurrence, profile=None, external_beneficiary=None):
    completed_ids = set(
        observations_for_beneficiary(
            occurrence=occurrence,
            profile=profile,
            external_beneficiary=external_beneficiary,
        ).values_list("checkpoint_id", flat=True)
    )
    for checkpoint in ordered_checkpoints(occurrence=occurrence).filter(required=True):
        if checkpoint.pk in completed_ids:
            continue
        if checkpoint.status == CheckpointStatus.OPEN:
            return NextCheckpointResult(checkpoint=checkpoint)
        if checkpoint.status == CheckpointStatus.PAUSED:
            return NextCheckpointResult(checkpoint=checkpoint, blocked_reason="paused")
        if checkpoint.status in {CheckpointStatus.PLANNED, CheckpointStatus.CLOSED}:
            return NextCheckpointResult(checkpoint=checkpoint, blocked_reason=checkpoint.status)
    return NextCheckpointResult(checkpoint=None)


def active_checkpoint_assignments(*, checkpoint):
    return CheckpointAssignment.objects.filter(checkpoint=checkpoint, ended_at__isnull=True).select_related(
        "profile", "assigned_by"
    )


def operator_checkpoint_context(*, profile, occurrence):
    return CheckpointAssignment.objects.filter(
        profile=profile,
        ended_at__isnull=True,
        checkpoint__occurrence=occurrence,
        checkpoint__active=True,
    ).select_related("checkpoint", "checkpoint__occurrence", "checkpoint__occurrence__activity")
