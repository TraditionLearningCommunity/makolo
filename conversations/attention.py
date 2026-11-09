from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch, Q
from django.utils import timezone

from .audience_services import profile_in_audience
from .core_models import ConversationLifecycle
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
ACTION_REASONS = frozenset({"respond", "acknowledge", "form", "resolve"})


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
    """Only an authorized, currently possible action may count as attention.

    Incoming audience membership alone does not imply a right to reply.
    A Point outside FROM_JOIN history must never enter attention/Now.
    Upcoming windows are not work due *now*; they can be shown as context.
    """
    from .point_interactions import point_interactions_for_profile
    from .point_services import point_visible_to

    at = at or timezone.now()
    if point.conversation.lifecycle != ConversationLifecycle.OPEN:
        return None
    if point.lifecycle not in ATTENTION_LIFECYCLES:
        return None
    if point.valid_until and point.valid_until <= at:
        return None
    if not point_visible_to(profile, point, at=at):
        return None

    capabilities = point_interactions_for_profile(profile, point, at=at)
    expected = bool(
        point.expected_action_audience_id
        and _profile_in_audience(
            profile, point.expected_action_audience,
            at=at, cache=audience_membership_cache,
        )
    )
    future = point.opens_at is not None and at < point.opens_at
    state = _profile_state(point, profile)
    if expected and capabilities["can_acknowledge"]:
        return "acknowledge"
    if expected and point.lifecycle == ConversationPointLifecycle.OPEN:
        if point.kind == ConversationPointKind.FORM_REQUEST:
            from .form_services import form_request_completed_for_profile, form_request_for_profile
            if not future and (not point.deadline_at or at < point.deadline_at):
                if form_request_for_profile(point, profile) is not None and not form_request_completed_for_profile(point, profile):
                    return "form"
        elif (
            point.response_mode != "none"
            and not future
            and capabilities["can_respond"]
            and capabilities["my_response"] is None
        ):
            return "respond"

    # Resolution is a real manager action, not a counter for every open
    # informational Point. Closing a response window creates a decision.
    if capabilities["can_resolve"] and (
        point.lifecycle == ConversationPointLifecycle.RESPONSE_CLOSED
        or (point.resolution_audience_id and not future)
        or (
            point.response_mode == "none"
            and point.kind not in {
                ConversationPointKind.INFORMATION, ConversationPointKind.EXCHANGE,
            }
            and not future
        )
    ):
        return "resolve"
    if state is not None and state.revisit_at is not None:
        return "revisit"
    return None


def attention_points_for_profile(profile, *, at=None, limit=100, only_actionable=False):
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
        .order_by("deadline_at", "-importance", "published_at")
    )
    items = []
    audience_membership_cache = {}
    conversation_visibility_cache = {}
    conversation_manage_cache = {}
    # The global list may start with many Points invisible to this viewer.
    # Stream until the *authorized* limit rather than returning a false zero.
    for point in candidates.iterator(chunk_size=120):
        reason = point_attention_reason(
            profile,
            point,
            at=at,
            audience_membership_cache=audience_membership_cache,
            conversation_visibility_cache=conversation_visibility_cache,
            conversation_manage_cache=conversation_manage_cache,
        )
        if reason and (not only_actionable or reason in ACTION_REASONS):
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
    return bool(attention_points_for_profile(profile, at=at, limit=1, only_actionable=True))


def conversation_attention_count(profile, *, at=None, limit=1000):
    return len(attention_points_for_profile(profile, at=at, limit=limit, only_actionable=True))


def conversation_attention_badge_count(profile, *, at=None, cap=10):
    """Return a UI badge count capped at the requested bound."""
    cap = max(int(cap), 1)
    return len(attention_points_for_profile(profile, at=at, limit=cap, only_actionable=True))
