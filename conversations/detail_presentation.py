"""Read-only, owner-scoped detail presentation for Makolo Conversations.

Never infer a member from an Audience rule, a permission from participation,
or a private media URL from a visible Point. Consumers only present these facts.
"""
from urllib.parse import urlsplit

from .core_models import (
    ConversationContextKind,
    ConversationParticipation,
    ConversationParticipationStatus,
)
from .list_presentation import _public_context_image
from .media_models import ConversationPointAttachment
from .media_services import can_download_attachment
from .point_models import ConversationPoint, ConversationPointLifecycle
from .point_services import point_visible_to
from .services import can_manage_conversation


def _safe_local_image(value):
    """No arbitrary remote/avatar metadata is loaded by the native client."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not parsed.path.startswith("/") or parsed.path.startswith("//")):
        return None
    return parsed.path


def conversation_subject_for_profile(profile, conversation, label):
    context = conversation.context
    kind = context.kind
    image = _public_context_image(conversation)
    identity = label
    target_id = None
    route = None
    if kind == ConversationContextKind.DIRECT:
        other = (
            context.direct_profile_b
            if context.direct_profile_a_id == profile.pk
            else context.direct_profile_a
        )
        if other and other.is_active:
            identity = other.full_name or other.username
            target_id = str(other.pk)
            route = f"/people/{other.pk}"
            # Profile publishes its portrait independently of Conversation.
            # The visibility policy decides; merely seeing a Conversation
            # does not grant access to this Profile media.
            from accounts.profile_visibility import ProfileVisibilityResolver
            from sharing.passport import profile_has_public_passport
            if (profile_has_public_passport(other)
                    and ProfileVisibilityResolver(owner=other, viewer=profile).field("avatar")):
                try:
                    image = _safe_local_image(other.avatar.url) if other.avatar else None
                except (ValueError, OSError):
                    image = None
    else:
        target = getattr(context, kind, None)
        if kind == ConversationContextKind.JOURNEY:
            target = context.journey
        if target is not None:
            target_id = str(target.pk)
        if kind == ConversationContextKind.SPACE and context.space_id:
            route = f"/spaces/{context.space.slug}"
        elif kind == ConversationContextKind.GROUP and context.group_id:
            route = f"/groups/{context.group_id}"
    return {
        "kind": kind,
        "label": identity,
        "id": target_id,
        "route": route,
        "image_url": image,
    }


def conversation_members_for_profile(profile, conversation):
    """Explicit participants only; never expand collective derived audiences."""
    kind = conversation.context.kind
    if kind == ConversationContextKind.DIRECT:
        ids = (
            conversation.context.direct_profile_a,
            conversation.context.direct_profile_b,
        )
        return {
            "scope": "direct",
            "people": [
                {"label": item.full_name or item.username, "is_me": item.pk == profile.pk}
                for item in ids if item is not None and item.is_active
            ],
        }
    if not can_manage_conversation(profile, conversation):
        # A Group member or Activity participant is not automatically
        # authorized to enumerate the other viewers or authorities.
        return {"scope": "restricted", "people": []}
    if kind == ConversationContextKind.GROUP:
        from groups.models import GroupMembership, GroupMembershipStatus
        memberships = GroupMembership.objects.filter(
            group=conversation.context.group,
            status=GroupMembershipStatus.ACTIVE,
            profile__is_active=True,
        )
        total = memberships.count()
        visible = memberships.select_related("profile").order_by(
            "joined_at", "pk",
        )[:30]
        return {
            "scope": "group",
            "total_count": total,
            "people": [
                {
                    "label": row.profile.full_name or row.profile.username,
                    "is_me": row.profile_id == profile.pk,
                }
                for row in visible
            ],
        }
    participants = (
        ConversationParticipation.objects.filter(
            conversation=conversation,
            status=ConversationParticipationStatus.ACTIVE,
            profile__is_active=True,
        ).select_related("profile").order_by("joined_at", "pk")[:30]
    )
    return {
        "scope": "explicit",
        "people": [
            {
                "label": participation.profile.full_name
                or participation.profile.username,
                "is_me": participation.profile_id == profile.pk,
            }
            for participation in participants
        ],
    }


def conversation_media_for_profile(profile, conversation, limit=24):
    """Private attachment index; every item is checked through its owner ACL."""
    points = ConversationPoint.objects.filter(
        conversation=conversation,
    ).exclude(lifecycle=ConversationPointLifecycle.DRAFT)
    candidates = ConversationPointAttachment.objects.filter(
        point__in=points,
    ).select_related(
        "point", "point__conversation", "point__visibility_audience",
        "point__response_audience", "response", "exchange_entry",
    ).order_by("-created_at", "-pk")[:120]
    results = []
    visibility_cache, audience_cache, history_cache, manager_cache = {}, {}, {}, {}
    for attachment in candidates:
        if not point_visible_to(profile, attachment.point,
                visibility_cache=visibility_cache, audience_cache=audience_cache,
                history_cache=history_cache):
            continue
        if not can_download_attachment(profile, attachment,
                visibility_cache=visibility_cache, audience_cache=audience_cache,
                history_cache=history_cache, manager_cache=manager_cache):
            continue
        results.append({
            "id": str(attachment.pk),
            "kind": attachment.kind,
            "name": attachment.original_name,
            "mime_type": attachment.mime_type,
            "size": attachment.size,
        })
        if len(results) >= limit:
            break
    return results


def conversation_resources_for_profile(profile, conversation, limit=8):
    """Only canonical ActivityResource metadata, never a shadow attachment."""
    context = conversation.context
    activity = None
    occurrence = None
    if context.kind == ConversationContextKind.ACTIVITY:
        activity = context.activity
    elif context.kind == ConversationContextKind.OCCURRENCE:
        occurrence = context.occurrence
        activity = occurrence.activity
    elif context.kind == ConversationContextKind.JOURNEY:
        occurrence = context.journey.occurrence
        activity = context.journey.activity
    if activity is None:
        return []
    from django.db.models import Q
    from preparation.models import ActivityResource, ResourceStatus
    from preparation.services import can_view_resource

    candidates = (
        ActivityResource.objects.filter(
            activity=activity, status=ResourceStatus.PUBLISHED,
        ).filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
        .select_related("activity", "occurrence")
        .order_by("-published_at", "-pk")[:70]
    )
    resources = []
    for item in candidates:
        if can_view_resource(profile, item):
            resources.append({
                "id": str(item.pk),
                "title": item.title,
                "kind": item.kind,
                "description": item.description[:240],
            })
            if len(resources) >= limit:
                break
    return resources


def conversation_detail_extra_for_profile(profile, conversation, label):
    """Composition of read models only. No new owner, state, or authority."""
    can_manage = can_manage_conversation(profile, conversation)
    return {
        "subject": conversation_subject_for_profile(profile, conversation, label),
        "members": conversation_members_for_profile(profile, conversation),
        "media": conversation_media_for_profile(profile, conversation),
        "resources": conversation_resources_for_profile(profile, conversation),
        "created_at": conversation.created_at,
        "can_manage": can_manage,
        "configuration": {
            "mode": conversation.get_mode_preset_display(),
            "entry": conversation.get_entry_mode_display(),
            "history": conversation.get_history_policy_display(),
            "lifecycle": conversation.get_lifecycle_display(),
            "created_by": (
                conversation.created_by.full_name
                or conversation.created_by.username
            ) if can_manage else None,
        },
        "share_path": f"/conversations/{conversation.pk}/",
        "share_requires_access": True,
    }
