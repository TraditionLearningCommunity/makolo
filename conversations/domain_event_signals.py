from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .contact_models import CommunicationRoute, CommunicationRouteStatus
from .core_models import (
    Conversation,
    ConversationContextKind,
    ConversationInvitation,
    ConversationInvitationStatus,
    ConversationLifecycle,
)
from .point_models import ConversationPoint, ConversationPointLifecycle


def _conversation_scope(conversation):
    try:
        context = conversation.context
    except Exception:
        return None, None
    space_id = None
    activity_id = None
    if context.kind == ConversationContextKind.SPACE:
        space_id = context.space_id
    elif context.kind == ConversationContextKind.GROUP:
        space_id = getattr(context.group, "space_id", None)
    elif context.kind == ConversationContextKind.ACTIVITY:
        activity_id = context.activity_id
        space_id = getattr(context.activity, "space_id", None)
    elif context.kind == ConversationContextKind.OCCURRENCE:
        activity = context.occurrence.activity
        activity_id = activity.pk
        space_id = activity.space_id
    elif context.kind == ConversationContextKind.DOSSIER:
        space_id = context.dossier.owning_space_id
    elif context.kind == ConversationContextKind.PROJECT:
        space_id = context.project.owning_space_id
    elif context.kind == ConversationContextKind.JOURNEY:
        activity = context.journey.activity
        activity_id = activity.pk
        space_id = activity.space_id
    elif context.kind == ConversationContextKind.ACTION_PROPOSAL:
        need = context.action_proposal.need
        activity_id = need.activity_id
        space_id = need.space_id or (need.activity.space_id if need.activity_id else None)
    return space_id, activity_id


def _emit(*, event_type, source_type, source_id, conversation, suffix, payload):
    space_id, activity_id = _conversation_scope(conversation)
    return emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=f"{source_type}:{source_id}:{suffix}"[:255],
        payload=payload,
        space_id=space_id,
        activity_id=activity_id,
    )


@receiver(pre_save, sender=Conversation)
def _conversation_before_save(sender, instance, **kwargs):
    instance._event_previous_lifecycle = (
        sender.objects.filter(pk=instance.pk).values_list("lifecycle", flat=True).first()
        if instance.pk and not instance._state.adding
        else None
    )


@receiver(post_save, sender=Conversation)
def _conversation_after_save(sender, instance, created, **kwargs):
    previous = getattr(instance, "_event_previous_lifecycle", None)
    current = instance.lifecycle
    event_type = None
    if current == ConversationLifecycle.OPEN and previous == ConversationLifecycle.DRAFT:
        event_type = DomainEventType.CONVERSATION_OPENED
    elif current == ConversationLifecycle.OPEN and previous == ConversationLifecycle.CLOSED:
        event_type = DomainEventType.CONVERSATION_REOPENED
    elif current == ConversationLifecycle.CLOSED and previous == ConversationLifecycle.OPEN:
        event_type = DomainEventType.CONVERSATION_CLOSED
    elif current == ConversationLifecycle.ARCHIVED and previous != ConversationLifecycle.ARCHIVED:
        event_type = DomainEventType.CONVERSATION_ARCHIVED
    if event_type:
        _emit(
            event_type=event_type,
            source_type="conversation",
            source_id=instance.pk,
            conversation=instance,
            suffix=f"{current}:{instance.updated_at.isoformat()}",
            payload={"conversation_id": str(instance.pk), "lifecycle": current},
        )


@receiver(pre_save, sender=ConversationPoint)
def _point_before_save(sender, instance, **kwargs):
    instance._event_previous_lifecycle = (
        sender.objects.filter(pk=instance.pk).values_list("lifecycle", flat=True).first()
        if instance.pk and not instance._state.adding
        else None
    )


@receiver(post_save, sender=ConversationPoint)
def _point_after_save(sender, instance, created, **kwargs):
    previous = getattr(instance, "_event_previous_lifecycle", None)
    current = instance.lifecycle
    mapping = {
        ConversationPointLifecycle.OPEN: DomainEventType.CONVERSATION_POINT_PUBLISHED,
        ConversationPointLifecycle.RESPONSE_CLOSED: DomainEventType.CONVERSATION_POINT_RESPONSE_CLOSED,
        ConversationPointLifecycle.RESOLVED: DomainEventType.CONVERSATION_POINT_RESOLVED,
        ConversationPointLifecycle.EXPIRED: DomainEventType.CONVERSATION_POINT_EXPIRED,
        ConversationPointLifecycle.CANCELLED: DomainEventType.CONVERSATION_POINT_CANCELLED,
        ConversationPointLifecycle.SUPERSEDED: DomainEventType.CONVERSATION_POINT_SUPERSEDED,
    }
    if current == previous or current == ConversationPointLifecycle.DRAFT:
        return
    event_type = mapping.get(current)
    if not event_type:
        return
    _emit(
        event_type=event_type,
        source_type="conversation_point",
        source_id=instance.pk,
        conversation=instance.conversation,
        suffix=f"{current}:{instance.updated_at.isoformat()}",
        payload={
            "conversation_id": str(instance.conversation_id),
            "point_id": str(instance.pk),
            "lifecycle": current,
        },
    )


@receiver(pre_save, sender=ConversationInvitation)
def _invitation_before_save(sender, instance, **kwargs):
    instance._event_previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        if instance.pk and not instance._state.adding
        else None
    )


@receiver(post_save, sender=ConversationInvitation)
def _invitation_after_save(sender, instance, created, **kwargs):
    previous = getattr(instance, "_event_previous_status", None)
    event_type = None
    if created and instance.status == ConversationInvitationStatus.PENDING:
        event_type = DomainEventType.CONVERSATION_INVITATION_CREATED
    elif previous == ConversationInvitationStatus.PENDING and instance.status == ConversationInvitationStatus.ACCEPTED:
        event_type = DomainEventType.CONVERSATION_INVITATION_ACCEPTED
    elif previous == ConversationInvitationStatus.PENDING and instance.status == ConversationInvitationStatus.DECLINED:
        event_type = DomainEventType.CONVERSATION_INVITATION_DECLINED
    if event_type:
        stamp = instance.created_at if created else instance.updated_at
        _emit(
            event_type=event_type,
            source_type="conversation_invitation",
            source_id=instance.pk,
            conversation=instance.conversation,
            suffix=f"{instance.status}:{stamp.isoformat()}",
            payload={
                "conversation_id": str(instance.conversation_id),
                "invitation_id": str(instance.pk),
                "status": instance.status,
            },
        )


@receiver(pre_save, sender=CommunicationRoute)
def _route_before_save(sender, instance, **kwargs):
    instance._event_previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        if instance.pk and not instance._state.adding
        else None
    )


@receiver(post_save, sender=CommunicationRoute)
def _route_after_save(sender, instance, created, **kwargs):
    previous = getattr(instance, "_event_previous_status", None)
    if created and instance.status == CommunicationRouteStatus.ACTIVE:
        event_type = DomainEventType.CONVERSATION_ROUTE_ADDED
    elif previous == CommunicationRouteStatus.ACTIVE and instance.status == CommunicationRouteStatus.RETIRED:
        event_type = DomainEventType.CONVERSATION_ROUTE_RETIRED
    else:
        return
    stamp = instance.created_at if created else instance.updated_at
    _emit(
        event_type=event_type,
        source_type="conversation_route",
        source_id=instance.pk,
        conversation=instance.conversation,
        suffix=f"{instance.status}:{stamp.isoformat()}",
        payload={
            "conversation_id": str(instance.conversation_id),
            "route_id": str(instance.pk),
            "status": instance.status,
        },
    )
