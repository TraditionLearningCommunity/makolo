from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import Access
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.models import Journey

from .models import OccurrenceQueue, QueueEntry, QueueEntryStatus, QueueStatus
from .permissions import user_can_manage_activity_operations


_INELIGIBLE_JOURNEY_STATUSES = {"rejected", "cancelled", "expired"}


def _subject_kwargs(*, profile=None, external_beneficiary=None):
    if bool(profile) == bool(external_beneficiary):
        raise ValidationError("La queue doit viser exactement un Profile ou un ExternalBeneficiary.")
    return {"profile": profile, "external_beneficiary": external_beneficiary}


def beneficiary_is_expected(*, queue, profile=None, external_beneficiary=None):
    occurrence = queue.occurrence
    journey_filters = {"activity": occurrence.activity, "occurrence": occurrence}
    access_filters = {"activity": occurrence.activity, "occurrence": occurrence}
    if profile is not None:
        journey_filters["beneficiary"] = profile
        access_filters["beneficiary"] = profile
    else:
        journey_filters["external_beneficiary"] = external_beneficiary
        access_filters["external_beneficiary"] = external_beneficiary
    return (
        Journey.objects.filter(**journey_filters).exclude(status__in=_INELIGIBLE_JOURNEY_STATUSES).exists()
        or Access.objects.filter(**access_filters).exists()
    )


def _require_manage(actor, queue):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("Authentification requise.")
    if not user_can_manage_activity_operations(actor, queue.occurrence.activity):
        raise PermissionDenied("Vous n’avez pas l’autorité Operations requise pour cette queue.")


def _emit(entry, event_type):
    queue = entry.queue
    activity = queue.occurrence.activity
    emit_domain_event(
        event_type=event_type,
        source_type="queue_entry",
        source_id=entry.pk,
        idempotency_key=f"queue-entry:{entry.pk}:{event_type}",
        space_id=activity.space_id,
        activity_id=activity.pk,
        occurred_at={
            DomainEventType.QUEUE_ENTERED: entry.entered_at,
            DomainEventType.QUEUE_CALLED: entry.called_at,
            DomainEventType.QUEUE_SERVED: entry.served_at,
            DomainEventType.QUEUE_EXPIRED: entry.ended_at,
            DomainEventType.QUEUE_CANCELLED: entry.ended_at,
        }[event_type],
        payload={
            "queue_id": str(queue.pk),
            "queue_entry_id": str(entry.pk),
            "occurrence_id": str(queue.occurrence_id),
            "checkpoint_id": str(queue.checkpoint_id) if queue.checkpoint_id else None,
            "subject_type": "profile" if entry.profile_id else "external_beneficiary",
            "status": entry.status,
            "sequence": entry.sequence,
        },
    )


@transaction.atomic
def enter_queue(
    *,
    actor,
    queue,
    profile=None,
    external_beneficiary=None,
    source="operator",
    client_reference="",
    allow_self=False,
):
    subject = _subject_kwargs(profile=profile, external_beneficiary=external_beneficiary)
    current = (
        OccurrenceQueue.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space", "checkpoint")
        .get(pk=queue.pk)
    )
    if allow_self:
        if profile is None or actor.pk != profile.pk:
            raise PermissionDenied("Un participant ne peut entrer que lui-même dans une queue.")
    else:
        _require_manage(actor, current)
    if current.status != QueueStatus.OPEN:
        raise ValidationError({"queue": "La queue doit être ouverte pour accepter une entrée."})
    if not beneficiary_is_expected(queue=current, **subject):
        raise ValidationError({"beneficiary": "Ce bénéficiaire n’est pas lié à cette Occurrence."})

    source = (source or "").strip()
    client_reference = (client_reference or "").strip()
    if source and client_reference:
        retry = QueueEntry.objects.filter(
            queue=current,
            entered_by=actor,
            source=source,
            client_reference=client_reference,
        ).first()
        if retry:
            if retry.profile_id != getattr(profile, "pk", None) or retry.external_beneficiary_id != getattr(external_beneficiary, "pk", None):
                raise ValidationError({"client_reference": "Cette référence idempotente est déjà utilisée pour un autre bénéficiaire."})
            return retry

    active = QueueEntry.objects.filter(queue=current, **subject, status__in=[QueueEntryStatus.WAITING, QueueEntryStatus.CALLED]).first()
    if active:
        return active

    sequence = current.next_sequence
    current.next_sequence += 1
    current.save(update_fields=["next_sequence", "updated_at"])
    entry = QueueEntry(
        queue=current,
        sequence=sequence,
        entered_by=actor,
        source=source,
        client_reference=client_reference,
        **subject,
    )
    try:
        entry.save()
    except IntegrityError as exc:
        active = QueueEntry.objects.filter(queue=current, **subject, status__in=[QueueEntryStatus.WAITING, QueueEntryStatus.CALLED]).first()
        if active:
            return active
        raise ValidationError("Conflit lors de l’entrée dans la queue.") from exc
    _emit(entry, DomainEventType.QUEUE_ENTERED)
    return entry


@transaction.atomic
def call_next(*, actor, queue):
    current = (
        OccurrenceQueue.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space", "checkpoint")
        .get(pk=queue.pk)
    )
    _require_manage(actor, current)
    if current.status != QueueStatus.OPEN:
        raise ValidationError({"queue": "La queue doit être ouverte pour appeler le prochain bénéficiaire."})
    entry = (
        QueueEntry.objects.select_for_update(of=("self",))
        .filter(queue=current, status=QueueEntryStatus.WAITING)
        .order_by("sequence", "id")
        .first()
    )
    if entry is None:
        return None
    entry.status = QueueEntryStatus.CALLED
    entry.called_by = actor
    entry.called_at = timezone.now()
    entry.save(update_fields=["status", "called_by", "called_at"])
    _emit(entry, DomainEventType.QUEUE_CALLED)
    return entry


def _locked_entry(entry):
    return (
        QueueEntry.objects.select_for_update(of=("self",))
        .select_related("queue", "queue__occurrence", "queue__occurrence__activity", "queue__occurrence__activity__space", "queue__checkpoint")
        .get(pk=entry.pk)
    )


@transaction.atomic
def serve_entry(*, actor, entry):
    current = _locked_entry(entry)
    _require_manage(actor, current.queue)
    if current.status != QueueEntryStatus.CALLED:
        raise ValidationError({"status": "Seule une entrée appelée peut être servie."})
    current.status = QueueEntryStatus.SERVED
    current.served_by = actor
    current.served_at = timezone.now()
    current.save(update_fields=["status", "served_by", "served_at"])
    _emit(current, DomainEventType.QUEUE_SERVED)
    return current


@transaction.atomic
def expire_entry(*, actor, entry):
    current = _locked_entry(entry)
    _require_manage(actor, current.queue)
    if current.status not in {QueueEntryStatus.WAITING, QueueEntryStatus.CALLED}:
        raise ValidationError({"status": "Seule une entrée active peut expirer."})
    current.status = QueueEntryStatus.EXPIRED
    current.ended_by = actor
    current.ended_at = timezone.now()
    current.save(update_fields=["status", "ended_by", "ended_at"])
    _emit(current, DomainEventType.QUEUE_EXPIRED)
    return current


@transaction.atomic
def cancel_entry(*, actor, entry, allow_self=False):
    current = _locked_entry(entry)
    if allow_self:
        if current.profile_id != actor.pk:
            raise PermissionDenied("Un participant ne peut annuler que sa propre entrée.")
    else:
        _require_manage(actor, current.queue)
    if current.status not in {QueueEntryStatus.WAITING, QueueEntryStatus.CALLED}:
        raise ValidationError({"status": "Seule une entrée active peut être annulée."})
    current.status = QueueEntryStatus.CANCELLED
    current.ended_by = actor
    current.ended_at = timezone.now()
    current.save(update_fields=["status", "ended_by", "ended_at"])
    _emit(current, DomainEventType.QUEUE_CANCELLED)
    return current
