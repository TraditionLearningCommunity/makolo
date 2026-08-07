from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Event, EventStatus
from .permissions import user_can_manage_event


def _ensure_can_manage(actor, event: Event) -> None:
    if not user_can_manage_event(actor, event):
        raise PermissionDenied("Vous ne pouvez pas gérer cet événement.")


@transaction.atomic
def publish_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)

    if event.status != EventStatus.DRAFT:
        raise ValidationError("Seul un brouillon peut être publié.")

    if event.end_at <= timezone.now():
        raise ValidationError("Un événement déjà terminé ne peut pas être publié.")

    event.full_clean()
    event.status = EventStatus.PUBLISHED
    event.published_at = timezone.now()
    event.cancelled_at = None
    event.save(
        update_fields=[
            "status",
            "published_at",
            "cancelled_at",
            "updated_at",
        ]
    )
    return event


@transaction.atomic
def cancel_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)

    if event.status not in {EventStatus.DRAFT, EventStatus.PUBLISHED}:
        raise ValidationError(
            "Seul un brouillon ou un événement publié peut être annulé."
        )

    event.status = EventStatus.CANCELLED
    event.cancelled_at = timezone.now()
    event.save(update_fields=["status", "cancelled_at", "updated_at"])
    return event


@transaction.atomic
def complete_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)

    if event.status != EventStatus.PUBLISHED:
        raise ValidationError("Seul un événement publié peut être terminé.")

    event.status = EventStatus.COMPLETED
    event.save(update_fields=["status", "updated_at"])
    return event
