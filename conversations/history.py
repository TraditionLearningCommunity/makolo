"""Owner-scoped C5 Point depth and search without duplicating domain history.

Signed keyset continuation binds the viewer, Conversation, search, filter and
snapshot ceiling. A Point's audience is re-evaluated on *every* page.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.utils import timezone

from .core_models import ConversationHistoryPolicy, ConversationParticipation, ConversationParticipationStatus
from .media_services import can_download_attachment
from .point_models import (
    ConversationPoint, ConversationPointLifecycle, ConversationResponseVisibility,
    ConversationPointResponseStatus, ConversationExchangeModerationState,
)
from .point_services import point_visible_to, point_resolution_visible_to
from .services import can_manage_conversation, can_view_conversation

_CURSOR_SALT = "conversation-point-depth-c5-v1"
_MAX_CURSOR_LENGTH = 4096
_MAX_PAGE = 60


def _cursor_scope(profile, conversation, *, query, section, limit):
    return {
        "version": 1, "viewer": str(profile.pk), "conversation": str(conversation.pk),
        "query": query, "section": section, "limit": limit,
    }


def _decode_cursor(raw, *, expected):
    if not isinstance(raw, str) or len(raw) > _MAX_CURSOR_LENGTH:
        raise ValidationError({"cursor": "Curseur invalide."})
    try:
        value = signing.loads(raw, salt=_CURSOR_SALT, max_age=7 * 86400)
        if not isinstance(value, dict) or any(value.get(key) != part for key, part in expected.items()):
            raise ValueError("cursor scope mismatch")
        snapshot = datetime.fromisoformat(value["snapshot"])
        date = datetime.fromisoformat(value["date"])
        pk = UUID(value["point"])
        if timezone.is_naive(snapshot) or timezone.is_naive(date):
            raise ValueError("timezone required")
        if date > snapshot:
            raise ValueError("invalid ordering")
    except (signing.BadSignature, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ValidationError({"cursor": "Ce résultat de recherche a changé. Recommencez."}) from exc
    return snapshot, date, pk


def _history_start(profile, conversation):
    """Explicit FROM_JOIN contracts never expose older entries via pagination."""
    if conversation.history_policy != ConversationHistoryPolicy.FROM_JOIN:
        return None
    if can_manage_conversation(profile, conversation):
        return None
    from .participant_services import profile_conversation_since
    # An accepted collective can now provide an auditable admission time,
    # never earlier than both consent and the real canonical membership.
    return profile_conversation_since(profile, conversation) or timezone.now()


def _matching_visible_content(profile, point, term):
    if not term:
        return True
    if term in (point.title or "").casefold() or term in (point.body or "").casefold():
        return True
    if point.lifecycle == ConversationPointLifecycle.RESOLVED and point_resolution_visible_to(profile, point):
        try:
            if term in (point.resolution.summary or "").casefold():
                return True
        except (AttributeError, ObjectDoesNotExist):
            pass

    # A private Exchange entry cannot cause an observable search hit for another
    # profile. Only text that the same profile can read is searched.
    if point.kind == "exchange":
        entries = point.exchange_entries.filter(
            moderation_state=ConversationExchangeModerationState.VISIBLE,
            body__icontains=term,
        )
        if can_manage_conversation(profile, point.conversation) or (
            point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS
        ):
            if entries.exists():
                return True
        elif point.response_visibility == ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES:
            if entries.filter(author=profile).exists():
                return True

    for item in point.attachments.filter(original_name__icontains=term).select_related(
        "response", "exchange_entry",
    )[:40]:
        if can_download_attachment(profile, item):
            return True
    return False


def page_points_for_profile(profile, conversation, *, query="", section="history", limit=25, cursor=None):
    """A bounded, signed, permission-checked read model over published Points."""
    if not can_view_conversation(profile, conversation):
        return {"results": [], "next_cursor": None}
    query = (query or "").strip()[:120]
    if section not in {"history", "all", "active"}:
        raise ValidationError({"section": "Filtre inconnu."})
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"limit": "Limite invalide."}) from exc
    if limit < 1 or limit > _MAX_PAGE:
        raise ValidationError({"limit": "Limite attendue entre 1 et 60."})

    scope = _cursor_scope(profile, conversation, query=query, section=section, limit=limit)
    snapshot = timezone.now()
    last_date = last_pk = None
    if cursor:
        snapshot, last_date, last_pk = _decode_cursor(cursor, expected=scope)
    earliest = _history_start(profile, conversation)
    points = ConversationPoint.objects.filter(
        conversation=conversation, published_at__isnull=False,
        published_at__lte=snapshot,
    ).exclude(lifecycle=ConversationPointLifecycle.DRAFT)
    if earliest is not None:
        points = points.filter(published_at__gte=earliest)
    if section == "history":
        points = points.exclude(lifecycle__in=(
            ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED,
        ))
    elif section == "active":
        points = points.filter(lifecycle__in=(
            ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED,
        ))
    if last_date is not None:
        points = points.filter(
            Q(published_at__lt=last_date) |
            Q(published_at=last_date, pk__lt=last_pk)
        )
    if query:
        points = points.filter(
            Q(title__icontains=query) | Q(body__icontains=query) |
            Q(resolution__summary__icontains=query) |
            Q(exchange_entries__body__icontains=query) |
            Q(attachments__original_name__icontains=query)
        ).distinct()

    points = points.select_related(
        "conversation__context", "published_by", "represented_space", "resolution",
        "visibility_audience", "resolution_audience",
        "response_audience", "expected_action_audience",
    ).prefetch_related("options", "responses").order_by("-published_at", "-pk")
    received = []
    # Keep scanning until there are limit+1 *visible* matches. A hard
    # candidate cap silently loses results when thousands of candidates
    # belong to another audience; it is not valid pagination.
    for point in points.iterator(chunk_size=100):
        if not point_visible_to(profile, point):
            continue
        if not _matching_visible_content(profile, point, query.casefold()):
            continue
        received.append(point)
        if len(received) > limit:
            break

    has_next = len(received) > limit
    result = received[:limit]
    next_cursor = None
    if has_next and result:
        marker = result[-1]
        next_cursor = signing.dumps(
            {
                **scope, "snapshot": snapshot.isoformat(),
                "date": marker.published_at.isoformat(), "point": str(marker.pk),
            },
            salt=_CURSOR_SALT,
            compress=True,
        )
    return {"results": result, "next_cursor": next_cursor}


def point_personal_result(profile, point):
    """Return only the viewer's response and permitted aggregate count."""
    cached = getattr(point, "_prefetched_objects_cache", {}).get("responses")
    if cached is not None:
        active = [
            row for row in cached
            if row.status == ConversationPointResponseStatus.ACTIVE
        ]
        mine = next((
            row for row in active if row.actor_id == profile.pk
            and row.represented_space_id is None
        ), None)
    else:
        mine = point.responses.filter(
            actor=profile, status=ConversationPointResponseStatus.ACTIVE,
            represented_space__isnull=True,
        ).order_by("-submitted_at").first()
        active = None
    manager = can_manage_conversation(profile, point.conversation)
    total = None
    if manager or point.response_visibility in (
        ConversationResponseVisibility.POINT_VIEWERS,
        ConversationResponseVisibility.AGGREGATE,
    ):
        total = len(active) if active is not None else point.responses.filter(
            status=ConversationPointResponseStatus.ACTIVE,
        ).count()
    return {
        "responded": mine is not None,
        "responded_at": mine.submitted_at if mine else None,
        "response_count": total,
    }
