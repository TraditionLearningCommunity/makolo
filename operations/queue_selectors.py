from django.db.models import Count, Q

from .models import OccurrenceQueue, QueueEntry, QueueEntryStatus
from .permissions import user_can_view_activity_operations


def queues_for_occurrence(*, occurrence):
    return OccurrenceQueue.objects.filter(occurrence=occurrence).select_related("occurrence", "checkpoint").order_by("label", "id")


def operator_queues_for_occurrence(*, user, occurrence):
    queryset = queues_for_occurrence(occurrence=occurrence)
    if not user_can_view_activity_operations(user, occurrence.activity):
        return queryset.none()
    return queryset


def active_entries(*, queue):
    return QueueEntry.objects.filter(
        queue=queue,
        status__in=[QueueEntryStatus.WAITING, QueueEntryStatus.CALLED],
    ).select_related("profile", "external_beneficiary", "entered_by", "called_by").order_by("sequence", "id")


def my_queue_entries(*, profile, occurrence):
    if not profile or not profile.is_authenticated:
        return QueueEntry.objects.none()
    return QueueEntry.objects.filter(queue__occurrence=occurrence, profile=profile).select_related("queue", "queue__checkpoint").order_by(
        "queue__label", "-entered_at"
    )


def queue_position(*, entry):
    if entry.status != QueueEntryStatus.WAITING:
        return None
    ahead = QueueEntry.objects.filter(
        queue=entry.queue,
        status=QueueEntryStatus.WAITING,
        sequence__lt=entry.sequence,
    ).count()
    return ahead + 1


def queue_snapshot(*, queue):
    counts = QueueEntry.objects.filter(queue=queue).aggregate(
        waiting=Count("id", filter=Q(status=QueueEntryStatus.WAITING)),
        called=Count("id", filter=Q(status=QueueEntryStatus.CALLED)),
        served=Count("id", filter=Q(status=QueueEntryStatus.SERVED)),
        expired=Count("id", filter=Q(status=QueueEntryStatus.EXPIRED)),
        cancelled=Count("id", filter=Q(status=QueueEntryStatus.CANCELLED)),
    )
    return counts
