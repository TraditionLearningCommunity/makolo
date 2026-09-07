from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from conversations.audience_services import (
    conversation_manager_ids,
    conversation_viewer_ids,
    resolve_audience_ids,
)
from conversations.core_models import ConversationInvitation, ConversationUserState
from conversations.point_models import (
    ConversationPoint,
    ConversationPointKind,
    ConversationPointResponseMode,
    ConversationPointResponseStatus,
)
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from questionnaires.models import FormRequestStatus

from .models import NotificationCategory, NotificationKind
from .services import create_notification


CONSUMER_NAME = "notifications.conversations"
EVENT_TYPES = {
    DomainEventType.CONVERSATION_POINT_PUBLISHED,
    DomainEventType.CONVERSATION_POINT_RESPONSE_CLOSED,
    DomainEventType.CONVERSATION_POINT_RESOLVED,
    DomainEventType.CONVERSATION_INVITATION_CREATED,
}
User = get_user_model()


def _muted_profile_ids(conversation, *, at=None):
    at = at or timezone.now()
    return set(
        ConversationUserState.objects.filter(
            conversation=conversation,
            muted_at__isnull=False,
        )
        .filter(Q(muted_until__isnull=True) | Q(muted_until__gt=at))
        .values_list("profile_id", flat=True)
    )


def _notify_profiles(*, event, conversation, profile_ids, title, message, template_key):
    muted = _muted_profile_ids(conversation)
    recipients = User.objects.filter(pk__in=set(profile_ids) - muted, is_active=True)
    action_url = reverse("conversations:detail", kwargs={"pk": conversation.pk})
    for recipient in recipients:
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title=title,
            message=message,
            action_url=action_url,
            dedup_key=f"conversation:{event.pk}:{recipient.pk}",
            metadata={"conversation_id": str(conversation.pk)},
            queue_email=False,
            domain_event=event,
            template_key=template_key,
        )


def _visible_profile_ids(point):
    viewers = conversation_viewer_ids(point.conversation)
    if point.visibility_audience_id:
        return viewers & resolve_audience_ids(point.visibility_audience)
    return viewers


def _outstanding_expected_profile_ids(point):
    if not point.expected_action_audience_id:
        return set()
    expected = resolve_audience_ids(point.expected_action_audience) & _visible_profile_ids(point)
    if not expected:
        return set()

    if point.kind == ConversationPointKind.FORM_REQUEST:
        completed = set(
            point.form_request_links.filter(
                target_profile_id__in=expected,
                form_request__status=FormRequestStatus.COMPLETED,
            ).values_list("target_profile_id", flat=True)
        )
        return expected - completed

    if point.requires_acknowledgement:
        acknowledged = set(
            point.user_states.filter(
                profile_id__in=expected,
                acknowledged_at__isnull=False,
            ).values_list("profile_id", flat=True)
        )
        return expected - acknowledged

    if point.response_mode != ConversationPointResponseMode.NONE:
        responded = set(
            point.responses.filter(
                actor_id__in=expected,
                represented_space__isnull=True,
                status=ConversationPointResponseStatus.ACTIVE,
            ).values_list("actor_id", flat=True)
        )
        return expected - responded
    return set()


def _consume_point(event):
    point = (
        ConversationPoint.objects.select_related(
            "conversation",
            "conversation__context",
            "expected_action_audience",
            "resolution_audience",
            "visibility_audience",
        )
        .filter(pk=event.payload.get("point_id"))
        .first()
    )
    if point is None:
        return

    visible_ids = _visible_profile_ids(point)
    if event.event_type == DomainEventType.CONVERSATION_POINT_PUBLISHED:
        if not point.expected_action_audience_id:
            return
        ids = resolve_audience_ids(point.expected_action_audience) & visible_ids
        ids.discard(point.published_by_id)
        _notify_profiles(
            event=event,
            conversation=point.conversation,
            profile_ids=ids,
            title="Une action vous attend",
            message="Un Point dans une Conversation Makolo attend votre réponse ou confirmation.",
            template_key="conversation.point.action_required",
        )
        return

    if event.event_type == DomainEventType.CONVERSATION_POINT_RESPONSE_CLOSED:
        if not _outstanding_expected_profile_ids(point):
            return
        managers = conversation_manager_ids(point.conversation) & visible_ids
        _notify_profiles(
            event=event,
            conversation=point.conversation,
            profile_ids=managers,
            title="Une coordination reste à régler",
            message="Des actions attendues sont restées incomplètes à la clôture d’un Point.",
            template_key="conversation.point.escalation",
        )
        return

    if point.resolution_audience_id:
        ids = resolve_audience_ids(point.resolution_audience) & visible_ids
    else:
        ids = visible_ids
    _notify_profiles(
        event=event,
        conversation=point.conversation,
        profile_ids=ids,
        title="Un Point a été résolu",
        message="Une décision ou un résultat est maintenant disponible dans cette Conversation.",
        template_key="conversation.point.resolved",
    )


def _consume_invitation(event):
    invitation = (
        ConversationInvitation.objects.select_related("conversation", "invitee")
        .filter(pk=event.payload.get("invitation_id"))
        .first()
    )
    if invitation is None or not invitation.invitee.is_active:
        return
    create_notification(
        recipient=invitation.invitee,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title="Invitation à une Conversation",
        message="Vous êtes invité à rejoindre une Conversation Makolo.",
        action_url=reverse("conversations:list"),
        dedup_key=f"conversation:{event.pk}:{invitation.invitee_id}",
        metadata={"conversation_id": str(invitation.conversation_id), "invitation_id": str(invitation.pk)},
        queue_email=False,
        domain_event=event,
        template_key="conversation.invitation.created",
    )


def consume_conversation_event(event):
    if event.event_type in {
        DomainEventType.CONVERSATION_POINT_PUBLISHED,
        DomainEventType.CONVERSATION_POINT_RESPONSE_CLOSED,
        DomainEventType.CONVERSATION_POINT_RESOLVED,
    }:
        _consume_point(event)
    elif event.event_type == DomainEventType.CONVERSATION_INVITATION_CREATED:
        _consume_invitation(event)


register_consumer(CONSUMER_NAME, consume_conversation_event, event_types=EVENT_TYPES)
