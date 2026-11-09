from __future__ import annotations

from dataclasses import dataclass, replace

from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound
from django.utils import timezone

from .attention import ACTION_REASONS, point_attention_reason
from .core_models import (
    Conversation,
    ConversationContextKind,
    ConversationParticipation,
    ConversationParticipationStatus,
    ConversationUserState,
)
from .point_models import (
    ConversationPoint, ConversationPointKind, ConversationPointLifecycle,
    ConversationPointResponse, ConversationPointResponseStatus,
    ConversationPointUserState, ConversationResponseVisibility,
)
from .media_models import ConversationPointAttachment
from .list_presentation import conversation_list_card
from .point_services import point_visible_to, point_resolution_visible_to
from .services import can_manage_conversation, can_view_conversation


@dataclass(frozen=True)
class ConversationRow:
    conversation: Conversation
    context_label: str
    attention_count: int
    latest_result: str
    all_clear: bool
    card: dict | None = None


@dataclass(frozen=True)
class ConversationSearchRow:
    conversation: Conversation
    context_label: str
    point: ConversationPoint | None
    rank: int
    card: dict | None = None


def conversations_for_context(profile, kind, context_pk):
    """Read-only contextual entry; never creates a Conversation or grants entry."""
    if kind == ConversationContextKind.DIRECT:
        filters = Q(context__direct_profile_a=profile, context__direct_profile_b_id=context_pk) | Q(
            context__direct_profile_b=profile, context__direct_profile_a_id=context_pk
        )
    else:
        field = {
            ConversationContextKind.SPACE: "space",
            ConversationContextKind.GROUP: "group",
            ConversationContextKind.ACTIVITY: "activity",
            ConversationContextKind.OCCURRENCE: "occurrence",
            ConversationContextKind.DOSSIER: "dossier",
            ConversationContextKind.PROJECT: "project",
            ConversationContextKind.JOURNEY: "journey",
            ConversationContextKind.ACTION_PROPOSAL: "action_proposal",
        }.get(kind)
        if field is None:
            raise NotFound("Contexte introuvable.")
        filters = Q(**{f"context__{field}_id": context_pk})
    try:
        candidates = list(
            Conversation.objects.select_related("context").filter(
                filters, context__kind=kind,
            ).order_by("-updated_at", "pk")[:200]
        )
    except (ValidationError, ValueError, TypeError):
        return []
    return [conversation for conversation in candidates if can_view_conversation(profile, conversation)][:50]



def visible_exchange_entries_for_profile(profile, point, *, limit=5):
    """A Point's visibility never implies access to every author's raw text."""
    if point.kind != ConversationPointKind.EXCHANGE or not point_visible_to(profile, point):
        return []
    entries = point.exchange_entries.filter(moderation_state="visible")
    if not can_manage_conversation(profile, point.conversation):
        if point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS:
            pass
        elif point.response_visibility == ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES:
            entries = entries.filter(author=profile)
        else:
            return []
    return list(reversed(list(entries.order_by("-created_at", "-pk")[:limit])))


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


def _list_projection_queryset(profile):
    active_points = ConversationPoint.objects.filter(
        lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}
    ).select_related(
        "conversation", "visibility_audience", "response_audience",
        "expected_action_audience", "resolution_audience",
    ).prefetch_related(
        Prefetch("attachments", queryset=ConversationPointAttachment.objects.select_related("response", "exchange_entry")),
        Prefetch(
            "responses",
            queryset=ConversationPointResponse.objects.filter(
                actor=profile, represented_space__isnull=True,
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
    resolved_points = ConversationPoint.objects.filter(
        lifecycle=ConversationPointLifecycle.RESOLVED
    ).select_related(
        "conversation", "resolution", "visibility_audience", "resolution_audience",
    ).prefetch_related(
        Prefetch("attachments", queryset=ConversationPointAttachment.objects.select_related("response", "exchange_entry")),
    ).order_by("-resolved_at")[:20]
    return (
        Conversation.objects.select_related(
            "context__space", "context__group", "context__activity", "context__occurrence__activity",
            "context__dossier", "context__project", "context__journey__activity",
            "context__action_proposal__need", "context__direct_profile_a", "context__direct_profile_b",
            "context__activity__event_vertical", "context__occurrence__activity__event_vertical",
        )
        .prefetch_related(
            Prefetch(
                "user_states",
                queryset=ConversationUserState.objects.filter(profile=profile),
                to_attr="m9c_profile_states",
            ),
            Prefetch(
                "explicit_participations",
                queryset=ConversationParticipation.objects.filter(
                    profile=profile,
                    status=ConversationParticipationStatus.ACTIVE,
                ),
                to_attr="m9c_active_participations",
            ),
            Prefetch("points", queryset=active_points, to_attr="m9c_active_points"),
            Prefetch("points", queryset=resolved_points, to_attr="m9c_resolved_points"),
        )
        .order_by("-updated_at")
    )


def _profile_state(conversation):
    prefetched = getattr(conversation, "m9c_profile_states", None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return None


def _can_view_list_conversation(profile, conversation):
    prefetched = getattr(conversation, "m9c_active_participations", None)
    if prefetched:
        return True
    return can_view_conversation(profile, conversation)


def _accessible_conversations(profile, *, include_archived=False, limit=300):
    qs = _list_projection_queryset(profile)[:limit]
    rows = []
    for conversation in qs:
        state = _profile_state(conversation)
        if state and state.hidden_at:
            continue
        if not include_archived and state and state.archived_at:
            continue
        if _can_view_list_conversation(profile, conversation):
            rows.append(conversation)
    return rows


def _latest_resolution_summary(conversation, profile):
    points = getattr(conversation, "m9c_resolved_points", None)
    if points is None:
        points = conversation.points.filter(lifecycle=ConversationPointLifecycle.RESOLVED).select_related("resolution", "visibility_audience").order_by("-resolved_at")[:20]
    for point in points[:20]:
        if point_resolution_visible_to(profile, point):
            try:
                return point.resolution.summary
            except Exception:
                continue
    return ""


def conversation_rows_for_profile(profile, *, archived=False, only_attention=False, limit=100):
    rows = []
    at = timezone.now()
    audience_membership_cache = {}
    conversation_visibility_cache = {}
    conversation_manage_cache = {}
    for conversation in _accessible_conversations(profile, include_archived=archived, limit=max(limit * 4, 100)):
        state = _profile_state(conversation)
        if archived and not (state and state.archived_at):
            continue
        attention = 0
        points = getattr(conversation, "m9c_active_points", None)
        if points is None:
            points = conversation.points.filter(lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}).select_related(
                "visibility_audience", "response_audience", "expected_action_audience", "resolution_audience"
            )[:200]
        for point in points[:200]:
            reason = point_attention_reason(
                profile, point, at=at,
                audience_membership_cache=audience_membership_cache,
                conversation_visibility_cache=conversation_visibility_cache,
                conversation_manage_cache=conversation_manage_cache,
            )
            if reason in ACTION_REASONS:
                attention += 1
        if only_attention and not attention:
            continue
        context_label = conversation_context_label(conversation, profile)
        latest_result = _latest_resolution_summary(conversation, profile)
        rows.append(
            ConversationRow(
                conversation=conversation,
                context_label=context_label,
                attention_count=attention,
                latest_result=latest_result,
                all_clear=attention == 0,
                card=conversation_list_card(
                    profile, conversation, context_label=context_label,
                    latest_result=latest_result, attention_count=attention,
                ),
            )
        )
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: (0 if row.attention_count else 1, -row.attention_count, -row.conversation.updated_at.timestamp()))
    return rows


def now_points_for_profile(profile, conversation, *, limit=100, visibility_cache=None, audience_cache=None, history_cache=None, attention_caches=None):
    if not can_view_conversation(profile, conversation):
        return []
    now = timezone.now()
    rows = []
    visibility_cache = visibility_cache if visibility_cache is not None else {}
    audience_cache = audience_cache if audience_cache is not None else {}
    history_cache = history_cache if history_cache is not None else {}
    attention_caches = attention_caches if attention_caches is not None else ({}, {}, {})
    points = conversation.points.filter(lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}).select_related(
        "published_by", "represented_space", "visibility_audience", "response_audience", "expected_action_audience", "resolution_audience"
    ).prefetch_related("options", "responses").order_by("deadline_at", "-importance", "published_at")[: max(limit * 3, 100)]
    for point in points:
        if not point_visible_to(
            profile, point, at=now, visibility_cache=visibility_cache,
            audience_cache=audience_cache, history_cache=history_cache,
        ):
            continue
        reason = point_attention_reason(
            profile, point, at=now,
            audience_membership_cache=attention_caches[0],
            conversation_visibility_cache=attention_caches[1],
            conversation_manage_cache=attention_caches[2],
        )
        if reason is None and point.kind != ConversationPointKind.INFORMATION:
            continue
        section = "pour_moi" if reason in {"respond", "acknowledge", "form"} else "a_regler" if reason == "resolve" else "a_savoir"
        rows.append({"point": point, "reason": reason, "section": section})
        if len(rows) >= limit:
            break
    return rows


def other_visible_points_for_profile(profile, conversation, *, excluded_ids=(), limit=50, visibility_cache=None, audience_cache=None, history_cache=None):
    """Visible open Points outside the owner's attention/essential selection."""
    if not can_view_conversation(profile, conversation):
        return []
    excluded = set(excluded_ids)
    visibility_cache = visibility_cache if visibility_cache is not None else {}
    audience_cache = audience_cache if audience_cache is not None else {}
    history_cache = history_cache if history_cache is not None else {}
    candidates = conversation.points.filter(
        lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED},
    ).select_related(
        "published_by", "represented_space", "visibility_audience", "response_audience", "expected_action_audience",
        "resolution_audience",
    ).prefetch_related("options", "responses").order_by("published_at", "pk")[: max(limit * 4, 100)]
    result = []
    for point in candidates:
        if point.pk in excluded or not point_visible_to(
            profile, point, visibility_cache=visibility_cache,
            audience_cache=audience_cache, history_cache=history_cache,
        ):
            continue
        result.append(point)
        if len(result) >= limit:
            break
    return result


def essential_points_for_profile(profile, conversation, *, limit=50):
    if not can_view_conversation(profile, conversation):
        return []
    candidates = conversation.points.filter(
        lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED, ConversationPointLifecycle.RESOLVED}
    ).select_related("published_by", "represented_space", "visibility_audience", "resolution").prefetch_related("options", "responses").order_by("-shared_pinned_at", "-resolved_at", "-published_at")[: max(limit * 3, 100)]
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
        if (point.lifecycle == ConversationPointLifecycle.RESOLVED and
                point_resolution_visible_to(profile, point)):
            try:
                resolution_summary = point.resolution.summary or ""
            except Exception:
                resolution_summary = ""
        if not (
            normalized in (point.title or "").casefold()
            or normalized in (point.body or "").casefold()
            or normalized in resolution_summary.casefold()
        ):
            continue
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


def search_conversations_for_profile(profile, query, *, limit=50, include_archived=False):
    """Privacy-safe global Conversation search with outcome/current-state precedence."""
    query = (query or "").strip()[:120]
    if not query or not getattr(profile, "is_authenticated", False):
        return []
    normalized = query.casefold()
    rows = []
    for conversation in _accessible_conversations(profile, include_archived=include_archived, limit=300):
        if include_archived:
            state = _profile_state(conversation)
            if not (state and state.archived_at):
                continue
        context_label = conversation_context_label(conversation, profile)
        haystack = " ".join((conversation.title_override or "", conversation.purpose or "", context_label)).casefold()
        if normalized in haystack:
            rows.append(ConversationSearchRow(conversation=conversation, context_label=context_label, point=None, rank=2))
        for point in search_conversation(profile, conversation, query, limit=5):
            if (point.lifecycle == ConversationPointLifecycle.RESOLVED and
                    point_resolution_visible_to(profile, point)):
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
    return [
        replace(
            row,
            card=conversation_list_card(
                profile, row.conversation, context_label=row.context_label,
                latest_result="", attention_count=0,
            ),
        )
        for row in rows[:limit]
    ]


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
