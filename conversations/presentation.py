from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from .attention import point_attention_reason
from .core_models import Conversation, ConversationContextKind
from .point_models import ConversationPoint, ConversationPointKind, ConversationPointLifecycle
from .point_services import point_visible_to
from .services import can_view_conversation


@dataclass(frozen=True)
class ConversationRow:
    conversation: Conversation
    context_label: str
    attention_count: int
    latest_result: str
    all_clear: bool


@dataclass(frozen=True)
class ConversationSearchRow:
    conversation: Conversation
    context_label: str
    point: ConversationPoint | None
    rank: int


def conversation_context_label(conversation, profile=None):
    context = conversation.context
    if context.kind == ConversationContextKind.SPACE:
        return context.space.name
    if context.kind == ConversationContextKind.GROUP:
        return context.group.name
    if context.kind == ConversationContextKind.ACTIVITY:
        return context.activity.title
    if context.kind == ConversationContextKind.OCCURRENCE:
        return context.occurrence.label or context.occurrence.activity.title
    if context.kind == ConversationContextKind.DOSSIER:
        return context.dossier.title
    if context.kind == ConversationContextKind.PROJECT:
        return context.project.title
    if context.kind == ConversationContextKind.JOURNEY:
        return context.journey.activity.title
    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        return context.action_proposal.need.title
    if context.kind == ConversationContextKind.DIRECT:
        if profile is not None and profile.pk == context.direct_profile_a_id:
            other = context.direct_profile_b
        elif profile is not None and profile.pk == context.direct_profile_b_id:
            other = context.direct_profile_a
        else:
            other = context.direct_profile_b if conversation.created_by_id == context.direct_profile_a_id else context.direct_profile_a
        return other.full_name or other.username
    return "Conversation"


def _accessible_conversations(profile, *, include_archived=False, limit=300):
    qs = Conversation.objects.select_related(
        "context__space", "context__group", "context__activity", "context__occurrence__activity",
        "context__dossier", "context__project", "context__journey__activity",
        "context__action_proposal__need", "context__direct_profile_a", "context__direct_profile_b",
    ).order_by("-updated_at")[:limit]
    rows = []
    for conversation in qs:
        state = conversation.user_states.filter(profile=profile).first()
        if state and state.hidden_at:
            continue
        if not include_archived and state and state.archived_at:
            continue
        if can_view_conversation(profile, conversation):
            rows.append(conversation)
    return rows


def _latest_resolution_summary(conversation, profile):
    points = conversation.points.filter(lifecycle=ConversationPointLifecycle.RESOLVED).select_related("resolution", "visibility_audience").order_by("-resolved_at")[:20]
    for point in points:
        if point_visible_to(profile, point):
            try:
                return point.resolution.summary
            except Exception:
                continue
    return ""


def conversation_rows_for_profile(profile, *, archived=False, only_attention=False, limit=100):
    rows = []
    for conversation in _accessible_conversations(profile, include_archived=archived, limit=max(limit * 4, 100)):
        state = conversation.user_states.filter(profile=profile).first()
        if archived and not (state and state.archived_at):
            continue
        attention = 0
        for point in conversation.points.filter(lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}).select_related(
            "visibility_audience", "response_audience", "expected_action_audience", "resolution_audience"
        )[:200]:
            if point_attention_reason(profile, point):
                attention += 1
        if only_attention and not attention:
            continue
        rows.append(
            ConversationRow(
                conversation=conversation,
                context_label=conversation_context_label(conversation, profile),
                attention_count=attention,
                latest_result=_latest_resolution_summary(conversation, profile),
                all_clear=attention == 0,
            )
        )
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: (0 if row.attention_count else 1, -row.attention_count, -row.conversation.updated_at.timestamp()))
    return rows


def now_points_for_profile(profile, conversation, *, limit=100):
    if not can_view_conversation(profile, conversation):
        return []
    now = timezone.now()
    rows = []
    points = conversation.points.filter(lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}).select_related(
        "visibility_audience", "response_audience", "expected_action_audience", "resolution_audience"
    ).order_by("deadline_at", "-importance", "published_at")[: max(limit * 3, 100)]
    for point in points:
        if not point_visible_to(profile, point, at=now):
            continue
        reason = point_attention_reason(profile, point, at=now)
        # "Maintenant" is personal: once a required Question/Request/Form has been
        # handled by this Profile, it must not linger as generic information merely
        # because other people may still have work. Information Points remain useful
        # in "À savoir" even when they do not demand an explicit action.
        if reason is None and point.kind != ConversationPointKind.INFORMATION:
            continue
        section = "pour_moi" if reason in {"respond", "acknowledge", "form", "revisit"} else "a_regler" if reason == "resolve" else "a_savoir"
        rows.append({"point": point, "reason": reason, "section": section})
        if len(rows) >= limit:
            break
    return rows


def essential_points_for_profile(profile, conversation, *, limit=50):
    if not can_view_conversation(profile, conversation):
        return []
    candidates = conversation.points.filter(
        lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED, ConversationPointLifecycle.RESOLVED}
    ).select_related("visibility_audience", "resolution").order_by("-shared_pinned_at", "-resolved_at", "-published_at")[: max(limit * 3, 100)]
    result = []
    for point in candidates:
        if not point_visible_to(profile, point):
            continue
        if point.shared_pinned_at or point.lifecycle == ConversationPointLifecycle.RESOLVED or point.importance in {"important", "critical"}:
            result.append(point)
        if len(result) >= limit:
            break
    return result


def search_conversation(profile, conversation, query, *, limit=50):
    if not can_view_conversation(profile, conversation):
        return []
    query = (query or "").strip()[:120]
    if not query:
        return []
    candidates = conversation.points.filter(
        Q(title__icontains=query) | Q(body__icontains=query) | Q(resolution__summary__icontains=query)
    ).select_related("visibility_audience", "resolution").distinct()[:200]
    scored = []
    normalized = query.casefold()
    for point in candidates:
        if not point_visible_to(profile, point):
            continue
        resolution_summary = ""
        if point.lifecycle == ConversationPointLifecycle.RESOLVED:
            try:
                resolution_summary = point.resolution.summary or ""
            except Exception:
                resolution_summary = ""
        if resolution_summary and normalized in resolution_summary.casefold():
            score = 0
        elif point.lifecycle in {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}:
            score = 1
        elif point.lifecycle == ConversationPointLifecycle.RESOLVED:
            score = 2
        elif point.lifecycle == ConversationPointLifecycle.SUPERSEDED:
            score = 5
        else:
            score = 3
        scored.append((score, -(point.published_at.timestamp() if point.published_at else 0), point))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:limit]]


def search_conversations_for_profile(profile, query, *, limit=50):
    """Privacy-safe global Conversation search with outcome/current-state precedence.

    The selector deliberately keeps the physical search implementation independent
    from the Conversation domain so SQLite can serve beta while PostgreSQL search
    can replace this implementation later without changing persisted truth.
    """

    query = (query or "").strip()[:120]
    if not query or not getattr(profile, "is_authenticated", False):
        return []
    normalized = query.casefold()
    rows = []
    for conversation in _accessible_conversations(profile, include_archived=False, limit=300):
        context_label = conversation_context_label(conversation, profile)
        haystack = " ".join((conversation.title_override or "", conversation.purpose or "", context_label)).casefold()
        if normalized in haystack:
            rows.append(ConversationSearchRow(conversation=conversation, context_label=context_label, point=None, rank=2))
        for point in search_conversation(profile, conversation, query, limit=5):
            if point.lifecycle == ConversationPointLifecycle.RESOLVED:
                try:
                    summary = point.resolution.summary or ""
                except Exception:
                    summary = ""
                rank = 0 if normalized in summary.casefold() else 2
            elif point.lifecycle in {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}:
                rank = 1
            else:
                rank = 3
            rows.append(ConversationSearchRow(conversation=conversation, context_label=context_label, point=point, rank=rank))
    rows.sort(
        key=lambda row: (
            row.rank,
            -(
                row.point.resolved_at.timestamp()
                if row.point is not None and row.point.resolved_at
                else row.point.published_at.timestamp()
                if row.point is not None and row.point.published_at
                else row.conversation.updated_at.timestamp()
            ),
        )
    )
    return rows[:limit]


def catch_up_summary(profile, conversation, *, since=None):
    if not can_view_conversation(profile, conversation):
        return None
    if since is None:
        state = conversation.user_states.filter(profile=profile).first()
        since = state.last_opened_at if state else None
    if since is None:
        return None
    visible = [point for point in conversation.points.filter(updated_at__gt=since).select_related("visibility_audience")[:200] if point_visible_to(profile, point)]
    resolved = sum(point.lifecycle == ConversationPointLifecycle.RESOLVED for point in visible)
    superseded = sum(point.lifecycle == ConversationPointLifecycle.SUPERSEDED for point in visible)
    important = sum(point.importance in {"important", "critical"} for point in visible)
    remaining = sum(bool(point_attention_reason(profile, point)) for point in visible if point.lifecycle in {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED})
    return {"resolved": resolved, "superseded": superseded, "important": important, "remaining": remaining}
