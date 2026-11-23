"""Viewer-scoped coordination overview, composed from existing Conversation owners.

This is a read model, never a second Inbox table or an authorization source.
Rows are capped *after* owner checks so a large unrelated tenant cannot hide
valid requests. All actionable decisions are revalidated by their own services.
"""
from django.db.models import Q
from django.utils import timezone

from .collective_models import ConversationCollectiveAccess, ConversationCollectiveStatus
from .core_models import (
    ConversationInvitation, ConversationInvitationStatus,
    ConversationJoinRequest, ConversationJoinRequestStatus,
    ConversationLifecycle, ConversationEntryMode,
)
from .services import can_manage_conversation, can_view_conversation, context_base_eligible


def _pending_until_now(queryset, now):
    return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def _managed(actor, conversation):
    return (
        conversation.lifecycle == ConversationLifecycle.OPEN
        and can_manage_conversation(actor, conversation)
    )


def _take_authorized(queryset, predicate, serializer, *, limit):
    rows = []
    for item in queryset.iterator(chunk_size=100):
        if not predicate(item):
            continue
        rows.append(serializer(item))
        if len(rows) > limit:
            break
    return rows[:limit], len(rows) > limit


def participation_inbox_for_profile(profile, *, limit=50):
    """Pending sent invitations and join requests, not a new participation truth.

    Incoming individual/collective invitations keep their existing response
    contract. A requester can see her own pending request without obtaining
    Conversation detail, names, participants or derived permissions.
    """
    if not getattr(profile, "is_authenticated", False) or not profile.is_active:
        return {
            "sent_results": [], "join_requests_to_decide": [],
            "my_join_requests": [], "more_sent": False,
            "more_join_requests": False, "more_my_requests": False,
        }
    limit = min(max(int(limit), 1), 50)
    now = timezone.now()

    personal, personal_more = _take_authorized(
        _pending_until_now(ConversationInvitation.objects.filter(
            created_by=profile, status=ConversationInvitationStatus.PENDING,
        ), now).select_related(
            "invitee", "conversation__context",
        ).order_by("-created_at", "-pk"),
        lambda invitation: _managed(profile, invitation.conversation),
        lambda invitation: {
            "id": str(invitation.pk),
            "conversation_id": str(invitation.conversation_id),
            "kind": "profile", "identifier": invitation.invitee.username,
            "status": invitation.status, "created_at": invitation.created_at,
        },
        limit=limit,
    )
    collective, collective_more = _take_authorized(
        _pending_until_now(ConversationCollectiveAccess.objects.filter(
            created_by=profile, status=ConversationCollectiveStatus.PENDING,
        ), now).select_related(
            "space", "group", "conversation__context",
        ).order_by("-created_at", "-pk"),
        lambda link: _managed(profile, link.conversation),
        lambda link: {
            "id": str(link.pk),
            "conversation_id": str(link.conversation_id),
            "kind": "space" if link.space_id else "group",
            "identifier": link.space.slug if link.space_id else link.group.slug,
            "status": link.status, "created_at": link.created_at,
        },
        limit=limit,
    )
    sent = sorted(
        personal + collective, key=lambda item: (
            item["created_at"], item["id"],
        ), reverse=True,
    )
    sent_more = personal_more or collective_more or len(sent) > limit

    to_decide, join_more = _take_authorized(
        ConversationJoinRequest.objects.filter(
            status=ConversationJoinRequestStatus.PENDING,
        ).select_related(
            "requester", "conversation__context",
        ).order_by("-created_at", "-pk"),
        lambda item: (
            _managed(profile, item.conversation)
            and item.conversation.entry_mode == ConversationEntryMode.REQUEST
        ),
        lambda item: {
            "id": str(item.pk),
            "conversation_id": str(item.conversation_id),
            # A requester is explicitly identifying herself to these
            # managers. Do not disclose a private full name.
            "identifier": item.requester.username,
            "status": item.status,
            "can_approve": bool(
                item.requester.is_active
                and context_base_eligible(item.requester, item.conversation.context)
            ),
            "created_at": item.created_at,
        },
        limit=limit,
    )
    my_requests, my_more = _take_authorized(
        ConversationJoinRequest.objects.filter(
            requester=profile, status=ConversationJoinRequestStatus.PENDING,
        ).select_related("conversation__context").order_by(
            "-created_at", "-pk",
        ),
        lambda item: True,
        lambda item: {
            "id": str(item.pk),
            # A submitted request is a private fact of the requester; it
            # does not grant access to the Conversation or its context.
            "conversation_id": str(item.conversation_id)
            if can_view_conversation(profile, item.conversation) else None,
            "status": item.status, "created_at": item.created_at,
        },
        limit=limit,
    )
    return {
        "sent_results": sent[:limit],
        "join_requests_to_decide": to_decide,
        "my_join_requests": my_requests,
        "more_sent": sent_more,
        "more_join_requests": join_more,
        "more_my_requests": my_more,
    }
