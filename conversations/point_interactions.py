"""Owner-authorized interaction projection for Conversation Points.

This is presentation of canonical Points/Responses, never a new response,
notification or domain-owner status. No individual's answers are exposed except
the viewer's own personal response. Aggregate poll counts respect visibility.
"""
from django.utils import timezone
from authorization.constants import PermissionCode
from authorization.services import can

from .core_models import ConversationLifecycle
from .point_models import (
    ConversationPointKind, ConversationPointLifecycle, ConversationPointResponseMode,
    ConversationPointResponseStatus, ConversationResponseVisibility,
)
from .point_services import point_visible_to, point_response_allowed
from .audience_services import profile_in_audience
from .services import can_manage_conversation


def _calculate_point_interactions(profile, point, *, at=None):
    at = at or timezone.now()
    if not point_visible_to(profile, point, at=at):
        return {
            "can_respond": False, "can_acknowledge": False,
            "can_close_responses": False, "can_resolve": False,
            "acknowledged": False, "revisit": False,
            "my_response": None, "poll_results": None,
            "response_window_open": False, "represented_responses": [],
            "response_hint": None,
        }
    # The list owner already prefetches viewer-specific active responses and
    # state. Do not reissue N per-Point reads on that path. Instance-local
    # attributes cannot be supplied by a client or shared across HTTP requests.
    prefetched_responses = getattr(point, "_attention_profile_responses", None)
    if prefetched_responses is None:
        mine = point.responses.filter(
            actor=profile, represented_space__isnull=True,
            status=ConversationPointResponseStatus.ACTIVE,
        ).order_by("-submitted_at", "-pk").first()
    else:
        mine = max(
            prefetched_responses,
            key=lambda row: (row.submitted_at, str(row.pk)),
            default=None,
        )
    prefetched_states = getattr(point, "_attention_profile_states", None)
    state = (
        (prefetched_states[0] if prefetched_states else None)
        if prefetched_states is not None
        else point.user_states.filter(profile=profile).first()
    )
    active = (
        point.conversation.lifecycle == ConversationLifecycle.OPEN
        and point.lifecycle == ConversationPointLifecycle.OPEN
        and (point.opens_at is None or point.opens_at <= at)
        and (point.deadline_at is None or point.deadline_at > at)
        and (point.valid_until is None or point.valid_until > at)
    )
    manager = can_manage_conversation(profile, point.conversation)
    resolution_authorized = manager and (
        not point.resolution_audience_id
        or profile_in_audience(profile, point.resolution_audience, at=at)
    )
    can_respond = bool(
        active and point.kind not in {ConversationPointKind.FORM_REQUEST}
        and point.response_mode != ConversationPointResponseMode.NONE
        and point_response_allowed(profile, point, at=at)
        and (mine is None or point.allow_response_change
             or point.kind == ConversationPointKind.EXCHANGE)
    )
    response_hint = None
    if point.response_mode != ConversationPointResponseMode.NONE and point.kind not in {
        ConversationPointKind.EXCHANGE, ConversationPointKind.FORM_REQUEST,
    }:
        if point.conversation.lifecycle != ConversationLifecycle.OPEN:
            response_hint = "Cette Conversation est fermée."
        elif point.lifecycle == ConversationPointLifecycle.RESOLVED:
            response_hint = "Ce Point est résolu."
        elif point.lifecycle == ConversationPointLifecycle.RESPONSE_CLOSED:
            response_hint = "Les réponses sont closes."
        elif point.lifecycle not in {ConversationPointLifecycle.OPEN}:
            response_hint = "Ce Point n'accepte plus de réponse."
        elif point.opens_at and at < point.opens_at:
            response_hint = "La période de réponse n'a pas encore commencé."
        elif point.deadline_at and at >= point.deadline_at:
            response_hint = "La date limite de réponse est dépassée."
        elif point.valid_until and at >= point.valid_until:
            response_hint = "Ce Point n'est plus valide."
        elif mine is not None and not point.allow_response_change:
            response_hint = "Votre réponse est déjà enregistrée."
        elif not point_response_allowed(profile, point, at=at):
            response_hint = "Ce Point ne vous demande pas de réponse."
    can_acknowledge = bool(
        point.conversation.lifecycle == ConversationLifecycle.OPEN
        and point.lifecycle in {
            ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED,
        }
        and point.requires_acknowledgement
        and (point.opens_at is None or point.opens_at <= at)
        and (point.valid_until is None or point.valid_until > at)
        and not (state and state.acknowledged_at)
        and (not point.expected_action_audience_id
             or profile_in_audience(profile, point.expected_action_audience, at=at))
    )
    can_close = bool(
        manager and point.conversation.lifecycle == ConversationLifecycle.OPEN
        and point.lifecycle == ConversationPointLifecycle.OPEN
        and point.response_mode != ConversationPointResponseMode.NONE
        and point.kind != ConversationPointKind.FORM_REQUEST
    )
    can_resolve = bool(
        resolution_authorized and point.conversation.lifecycle == ConversationLifecycle.OPEN
        and point.lifecycle in {
            ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED,
        }
    )
    represented_responses = []
    if point_response_allowed(profile, point, at=at):
        for response in point.responses.filter(
            status=ConversationPointResponseStatus.ACTIVE,
            represented_space__isnull=False,
        ).select_related("represented_space"):
            if can(
                profile, PermissionCode.SPACE_CONVERSATIONS_PUBLISH,
                space=response.represented_space,
            ):
                represented_responses.append({
                    "space_id": str(response.represented_space_id),
                    "value": response.value,
                    "submitted_at": response.submitted_at,
                })
    response_window_open = bool(
        active and point.response_mode != ConversationPointResponseMode.NONE
        and point.kind != ConversationPointKind.FORM_REQUEST
        and point_response_allowed(profile, point, at=at)
    )
    poll_results = None
    if point.kind == ConversationPointKind.POLL and (
        manager or point.response_visibility in {
            ConversationResponseVisibility.AGGREGATE,
            ConversationResponseVisibility.POINT_VIEWERS,
        }
    ):
        option_ids = [str(option.pk) for option in point.options.all()]
        counts = {key: 0 for key in option_ids}
        total = 0
        for response in point.responses.filter(status=ConversationPointResponseStatus.ACTIVE).only("value"):
            total += 1
            choices = (
                response.value if point.response_mode == ConversationPointResponseMode.MULTIPLE_CHOICE
                and isinstance(response.value, list)
                else [response.value]
            )
            for key in choices:
                if str(key) in counts:
                    counts[str(key)] += 1
        poll_results = {"response_count": total, "counts": counts}
    return {
        "can_respond": can_respond,
        "response_hint": response_hint,
        "response_window_open": response_window_open,
        "represented_responses": represented_responses,
        "can_acknowledge": can_acknowledge,
        "can_close_responses": can_close,
        "can_resolve": can_resolve,
        "acknowledged": bool(state and state.acknowledged_at),
        "revisit": bool(state and state.revisit_at),
        "my_response": (
            {"value": mine.value, "submitted_at": mine.submitted_at}
            if mine is not None else None
        ),
        "poll_results": poll_results,
    }


def point_interactions_for_profile(profile, point, *, at=None):
    """Memoize repeated Web/Flutter projection reads on this Point instance only.

    The same instance belongs to one request; never cache across HTTP requests,
    Profiles or explicit time-based permission evaluations.
    """
    if at is not None:
        return _calculate_point_interactions(profile, point, at=at)
    viewer = getattr(profile, "pk", None)
    cached = getattr(point, "_profile_point_interactions_cache", None)
    if cached is not None and cached[0] == viewer:
        return cached[1]
    result = _calculate_point_interactions(profile, point)
    point._profile_point_interactions_cache = (viewer, result)
    return result
