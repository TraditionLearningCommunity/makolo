from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch, Q
from django.utils import timezone

from .audience_services import profile_in_audience
from .point_models import (
    ConversationPoint,
    ConversationPointKind,
    ConversationPointLifecycle,
    ConversationPointResponse,
    ConversationPointResponseStatus,
    ConversationPointUserState,
)
from .services import can_manage_conversation, can_view_conversation


ATTENTION_LIFECYCLES = {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}


@dataclass(frozen=True)
class ConversationAttentionItem:
    point_id: object
    conversation_id: object
    reason: str
    deadline_at: object
    importance: str


def _subject_has_active_response(point, profile):
    prefetched = getattr(point, "_attention_profile_responses", None)
    if prefetched is not None:
        return bool(prefetched)
    return point.responses.filter(
        actor=profile,
        represented_space__isnull=True,
        status=ConversationPointResponseStatus.ACTIVE,
    ).exists()


def _profile_state(point, profile):
    prefetched = getattr(point, "_attention_profile_states", None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return point.user_states.filter(profile=profile).first()


def _cached(cache, key, resolver):
    if cache is None:
        return resolver()
    if key not in cache:
        cache[key] = resolver()
    return cache[key]


def _profile_in_audience(
    profile,
    audience,
    *,
    at,
    cache=None,
):
    if audience is None:
        return False
    return _cached(
        cache,
        audience.pk,
        lambda: profile_in_audience(profile, audience, at=at),
    )


def _conversation_visible(profile, conversation, *, cache=None):
    return _cached(
        cache,
        conversation.pk,
        lambda: can_view_conversation(profile, conversation),
    )


def _conversation_manageable(profile, conversation, *, cache=None):
    return _cached(
        cache,
        conversation.pk,
        lambda: can_manage_conversation(profile, conversation),
    )


def point_attention_reason(
    profile,
    point,
    *,
    at=None,
    audience_membership_cache=None,
    conversation_visibility_cache=None,
    conversation_manage_cache=None,
):
    at = at or timezone.now()
    if point.lifecycle not in ATTENTION_LIFECYCLES:
        return None
    if not _conversation_visible(
        profile,
        point.conversation,
        cache=conversation_visibility_cache,
    ):
        return None
    if point.visibility_audience_id and not _profile_in_audience(
        profile,
        point.visibility_audience,
        at=at,
        cache=audience_membership_cache,
    ):
        return None
    if point.valid_until and at >= point.valid_until:
        return None

    expected = bool(
        point.expected_action_audience_id
        and _profile_in_audience(
            profile,
            point.expected_action_audience,
            at=at,
            cache=audience_membership_cache,
        )
    )
    state = _profile_state(point, profile)

    if point.requires_acknowledgement and expected:
        if state is None or state.acknowledged_at is None:
            return "acknowledge"

    if point.lifecycle == ConversationPointLifecycle.OPEN and expected:
        if point.kind == ConversationPointKind.FORM_REQUEST:
            from .form_services import form_request_completed_for_profile

            if not form_request_completed_for_profile(point, profile):
                return "form"
        elif point.response_mode != "none" and not _subject_has_active_response(point, profile):
            if not point.deadline_at or at < point.deadline_at:
                return "respond"

    if point.resolution_audience_id and _profile_in_audience(
        profile,
        point.resolution_audience,
        at=at,
        cache=audience_membership_cache,
    ):
        if _conversation_manageable(
            profile,
            point.conversation,
            cache=conversation_manage_cache,
        ):
            return "resolve"

    if state is not None and state.revisit_at is not None:
        return "revisit"
    return None

def attention_points_for_profile(profile, *, at=None, limit=100):
    if not getattr(profile, "is_authenticated", False):
        return []
    at = at or timezone.now()
    candidates = (
        ConversationPoint.objects.filter(lifecycle__in=ATTENTION_LIFECYCLES)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
        .select_related(
            "conversation",
            "visibility_audience",
            "response_audience",
            "expected_action_audience",
            "resolution_audience",
        )
        .prefetch_related(
            Prefetch(
                "responses",
                queryset=ConversationPointResponse.objects.filter(
                    actor=profile,
                    represented_space__isnull=True,
                    status=ConversationPointResponseStatus.ACTIVE,
                ),
                to_attr="_attention_profile_responses",
            ),
            Prefetch(
                "user_states",
                queryset=ConversationPointUserState.objects.filter(profile=profile),
                to_attr="_attention_profile_states",
            ),
        )
        .order_by("deadline_at", "-importance", "published_at")[
            : max(int(limit or 100) * 4, 100)
        ]
    )
    items = []
    audience_membership_cache = {}
    conversation_visibility_cache = {}
    conversation_manage_cache = {}
    for point in candidates:
        reason = point_attention_reason(
            profile,
            point,
            at=at,
            audience_membership_cache=audience_membership_cache,
            conversation_visibility_cache=conversation_visibility_cache,
            conversation_manage_cache=conversation_manage_cache,
        )
        if reason:
            items.append(
                ConversationAttentionItem(
                    point_id=point.pk,
                    conversation_id=point.conversation_id,
                    reason=reason,
                    deadline_at=point.deadline_at,
                    importance=point.importance,
                )
            )
            if len(items) >= limit:
                break
    return items


def has_conversation_attention(profile, *, at=None):
    """Return whether at least one Point currently needs this Profile.

    This is a Presentation signal for shells. It intentionally preserves the
    Conversation attention semantics instead of treating unread activity as
    attention, and stops as soon as one qualifying Point is found.
    """
    return bool(attention_points_for_profile(profile, at=at, limit=1))


def conversation_attention_count(profile, *, at=None, limit=1000):
    return len(attention_points_for_profile(profile, at=at, limit=limit))


def conversation_attention_badge_count(profile, *, at=None, cap=10):
    """Return a UI badge count capped at the requested bound."""
    cap = max(int(cap), 1)
    return len(attention_points_for_profile(profile, at=at, limit=cap))
