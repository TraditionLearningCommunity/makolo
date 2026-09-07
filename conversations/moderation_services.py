from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .point_models import ConversationExchangeModerationState, PointExchangeEntry
from .services import can_moderate_conversation


@transaction.atomic
def moderate_exchange_entry(*, actor, entry: PointExchangeEntry, state: str):
    """Moderate one free-exchange entry without deleting shared history."""

    if state not in ConversationExchangeModerationState.values:
        raise ValidationError({"state": "État de modération inconnu."})
    locked = (
        PointExchangeEntry.objects.select_for_update(of=("self",))
        .select_related("point__conversation__context")
        .get(pk=entry.pk)
    )
    if not can_moderate_conversation(actor, locked.point.conversation):
        raise PermissionDenied("Vous ne pouvez pas modérer cet échange.")
    if locked.moderation_state == state:
        return locked

    locked.moderation_state = state
    if state == ConversationExchangeModerationState.REMOVED:
        locked.removed_at = timezone.now()
        locked.removed_by = actor
    else:
        locked.removed_at = None
        locked.removed_by = None
    locked.save(update_fields=["moderation_state", "removed_at", "removed_by"])
    return locked
