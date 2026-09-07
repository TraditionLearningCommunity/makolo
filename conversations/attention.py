from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from .audience_services import profile_in_audience
from .point_models import (
    ConversationPoint,
    ConversationPointKind,
    ConversationPointLifecycle,
    ConversationPointResponseStatus,
)
from .point_services import point_expected_from, point_visible_to
from .services import can_manage_conversation


ATTENTION_LIFECYCLES = {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}


@dataclass(frozen=True)
class ConversationAttentionItem:
    point_id: object
    conversation_id: object
    reason: str
    deadline_at: object
    importance: str


def _subject_has_active_response(point, profile):
    return point.responses.filter(
        actor=profile,
        represented_space__isnull=True,
        status=ConversationPointResponseStatus.ACTIVE,
    ).exists()


def point_attention_reason(profile, point, *, at=None):
    at = at or timezone.now()
    if point.lifecycle not in ATTENTION_LIFECYCLES or not point_visible_to(profile, point, at=at):
        return None
    if point.valid_until and at >= point.valid_until:
        return None
    if point.requires_acknowledgement and point_expected_from(profile, point, at=at):
        acknowledged = point.user_states.filter(profile=profile, acknowledged_at__isnull=False).exists()
        if not acknowledged:
            return "acknowledge"
    if point.lifecycle == ConversationPointLifecycle.OPEN and point_expected_from(profile, point, at=at):
        if point.kind == ConversationPointKind.FORM_REQUEST:
            # J6 supplies per-profile FormRequest completion; until then this stays visible but not falsely completed.
            return "form"
        if point.response_mode != "none" and not _subject_has_active_response(point, profile):
            if not point.deadline_at or at < point.deadline_at:
                return "respond"
    if point.resolution_audience_id and profile_in_audience(profile, point.resolution_audience, at=at):
        if can_manage_conversation(profile, point.conversation) and point.lifecycle in ATTENTION_LIFECYCLES:
            return "resolve"
    revisit = point.user_states.filter(profile=profile, revisit_at__isnull=False).exists()
    if revisit:
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
        .order_by("deadline_at", "-importance", "published_at")[: max(int(limit or 100) * 4, 100)]
    )
    items = []
    for point in candidates:
        reason = point_attention_reason(profile, point, at=at)
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


def conversation_attention_count(profile, *, at=None):
    return len(attention_points_for_profile(profile, at=at, limit=1000))
