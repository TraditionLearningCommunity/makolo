from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .contact_models import CommunicationRoute, CommunicationRouteStatus
from .point_models import ConversationPoint, ConversationPointLifecycle
from .services import can_manage_conversation, can_manage_conversation_routes


@transaction.atomic
def cancel_point(*, actor, point: ConversationPoint):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=point.pk)
    if not can_manage_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas annuler ce Point.")
    if locked.lifecycle == ConversationPointLifecycle.CANCELLED:
        return locked
    if locked.lifecycle not in {
        ConversationPointLifecycle.OPEN,
        ConversationPointLifecycle.RESPONSE_CLOSED,
    }:
        raise ValidationError("Ce Point ne peut plus être annulé dans son état actuel.")
    now = timezone.now()
    locked.lifecycle = ConversationPointLifecycle.CANCELLED
    locked.cancelled_at = now
    locked.response_closed_at = locked.response_closed_at or now
    locked._allow_lifecycle_transition = True
    locked.save(update_fields=["lifecycle", "cancelled_at", "response_closed_at", "updated_at"])
    return locked


@transaction.atomic
def retire_communication_route(*, actor, route: CommunicationRoute):
    locked = CommunicationRoute.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=route.pk)
    if not can_manage_conversation_routes(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas retirer cette route externe.")
    if locked.status == CommunicationRouteStatus.RETIRED:
        return locked
    locked.status = CommunicationRouteStatus.RETIRED
    locked.save(update_fields=["status", "updated_at"])
    return locked
