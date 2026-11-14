"""Request-scoped attention lens over canonical Conversations.

The lens is ABOVE the chronological Point feed. It never reorders Point
history, creates a second lifecycle, or grants access by being in a summary.
"""
from datetime import timedelta

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from .attention import ACTION_REASONS, point_attention_reason
from .audience_services import profile_in_audience
from .core_models import ConversationLifecycle
from .point_models import (
    ConversationPoint, ConversationPointKind, ConversationPointLifecycle,
    ConversationPointResponseMode, ConversationPointResponseStatus,
)
from .point_services import (
    point_visible_to, point_resolution_visible_to, point_response_allowed,
)
from .services import can_view_conversation

REASON_LABELS = {
    "respond": "Répondre",
    "acknowledge": "Confirmer la prise de connaissance",
    "form": "Remplir le questionnaire",
    "resolve": "Décider et résoudre",
    "revisit": "À revoir",
    "upcoming": "À venir",
    "information": "Information récente",
    "result": "Résultat disponible",
}


def _safe_preview(point, profile, reason):
    if reason == "result" and point_resolution_visible_to(profile, point):
        try:
            return (point.resolution.summary or "Résultat disponible")[:160]
        except (AttributeError, ObjectDoesNotExist):
            pass
    return (point.title or point.body or point.get_kind_display() or "Point")[:160]


def _upcoming_action_is_real(profile, point, *, at):
    """Future window is knowledge only if the targeted Profile can act then."""
    if not point.expected_action_audience_id or not profile_in_audience(
        profile, point.expected_action_audience, at=at,
    ):
        return False
    if point.requires_acknowledgement and not point.user_states.filter(
        profile=profile, acknowledged_at__isnull=False,
    ).exists():
        return True
    if point.kind == ConversationPointKind.FORM_REQUEST:
        from .form_services import (
            form_request_completed_for_profile, form_request_for_profile,
        )
        return (
            form_request_for_profile(point, profile) is not None
            and not form_request_completed_for_profile(point, profile)
        )
    if point.response_mode != ConversationPointResponseMode.NONE and point_response_allowed(
        profile, point, at=at,
    ):
        return not point.responses.filter(
            actor=profile, represented_space__isnull=True,
            status=ConversationPointResponseStatus.ACTIVE,
        ).exists()
    return False


def _info_reason(profile, point, *, at, last_opened):
    if (
        point.lifecycle == ConversationPointLifecycle.OPEN
        and point.opens_at and at < point.opens_at
    ):
        # Published metadata is not an already-open piece of information.
        # The only possible early signal is a truly actionable future window.
        return (
            "upcoming" if point.opens_at <= at + timedelta(days=7)
            and _upcoming_action_is_real(profile, point, at=at)
            else None
        )
    if point.lifecycle == ConversationPointLifecycle.RESOLVED:
        if point.resolved_at and (last_opened is None or point.resolved_at > last_opened):
            return "result"
    if (
        point.kind == ConversationPointKind.INFORMATION
        and point.lifecycle == ConversationPointLifecycle.OPEN
        and point.published_at
        and (last_opened is None or point.published_at > last_opened)
    ):
        return "information"
    return None


def _deadline_state(point, at):
    deadline = point.deadline_at
    if deadline is None:
        return "none"
    if deadline <= at:
        return "passed"
    if timezone.localtime(deadline).date() == timezone.localtime(at).date():
        return "today"
    if deadline <= at + timedelta(days=3):
        return "soon"
    return "later"


def conversation_attention_sections(profile, conversation, *, at=None, limit=80):
    """Returns viewer-only cards, with exactly one bucket per visible Point."""
    if not can_view_conversation(profile, conversation):
        return {
            "for_me": [], "to_resolve": [], "to_know": [],
            "action_count": 0, "all_clear": True,
        }
    at = at or timezone.now()
    state = conversation.user_states.filter(profile=profile).first()
    opened = state.last_opened_at if state else None
    # Information is bounded by a time window; old history stays in the
    # chronological feed, not a second ever-growing notification inbox.
    info_from = at - timedelta(days=14)
    if opened is not None and opened > info_from:
        info_from = opened
    base = ConversationPoint.objects.filter(
        conversation=conversation,
    ).select_related(
        "conversation", "visibility_audience", "response_audience",
        "expected_action_audience", "resolution_audience", "published_by",
    )
    # Old open Points remain eligible regardless of publication age. Stream
    # them rather than materializing an unbounded full history in memory.
    active = base.filter(lifecycle__in={
        ConversationPointLifecycle.OPEN,
        ConversationPointLifecycle.RESPONSE_CLOSED,
    }).order_by("deadline_at", "pk")
    recent_results = base.filter(
        lifecycle=ConversationPointLifecycle.RESOLVED,
        resolved_at__gte=info_from,
    ).order_by("-resolved_at", "-pk")[:max(limit * 2, 100)]
    older_revisit = base.filter(
        user_states__profile=profile,
        user_states__revisit_at__isnull=False,
    ).distinct().order_by("-user_states__revisit_at")[:max(limit * 2, 100)]
    seen = set()

    def current_candidates():
        for source in (
            active.iterator(chunk_size=100),
            recent_results,
            older_revisit,
        ):
            for point in source:
                if point.pk in seen:
                    continue
                seen.add(point.pk)
                yield point

    sections = {"for_me": [], "to_resolve": [], "to_know": []}
    visibility_cache, audience_cache, history_cache = {}, {}, {}
    total_actions = 0
    for point in current_candidates():
        if not point_visible_to(
            profile, point, at=at, visibility_cache=visibility_cache,
            audience_cache=audience_cache, history_cache=history_cache,
        ):
            continue
        reason = point_attention_reason(profile, point, at=at)
        if reason not in ACTION_REASONS and point.user_states.filter(
            profile=profile, revisit_at__isnull=False,
        ).exists():
            reason = "revisit"
        if reason in {"respond", "acknowledge", "form"}:
            bucket = "for_me"
        elif reason == "resolve":
            bucket = "to_resolve"
        else:
            if reason != "revisit":
                reason = _info_reason(profile, point, at=at, last_opened=info_from)
            if reason is None:
                continue
            bucket = "to_know"
        entry = {
            "id": str(point.pk),
            "conversation_id": str(conversation.pk),
            "label": _safe_preview(point, profile, reason),
            "reason": reason,
            "reason_label": REASON_LABELS[reason],
            "deadline_at": point.deadline_at,
            "deadline_state": _deadline_state(point, at),
            "published_at": point.published_at,
            "actionable": reason in ACTION_REASONS,
            "url": (
                reverse("conversations:detail", kwargs={"pk": conversation.pk})
                + f"?focus={point.pk}#point-{point.pk}"
            ),
        }
        if reason in ACTION_REASONS:
            total_actions += 1
        if len(sections[bucket]) < limit:
            sections[bucket].append(entry)

    # Attention cards are *not* the timeline. Order the required actions
    # by the next real deadline, not publication date or urgency inventions.
    def order(item):
        deadline = item["deadline_at"]
        return (deadline is None, deadline or at, item["published_at"] or at)
    for bucket in ("for_me", "to_resolve"):
        sections[bucket].sort(key=order)
    displayed_actions = len(sections["for_me"]) + len(sections["to_resolve"])
    return {
        **sections,
        "action_count": total_actions,
        "more_actions": total_actions > displayed_actions,
        "all_clear": total_actions == 0,
    }
