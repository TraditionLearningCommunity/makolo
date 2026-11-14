"""Minimal, viewer-scoped list presentation for Conversations.

This module composes already-owned context, Point and media facts. It never
copies ownership, invents media or grants access from a Conversation title.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from activities.models import ActivityStatus, ActivityVisibility

from .core_models import ConversationContextKind
from .media_services import can_download_attachment
from .point_models import ConversationPointKind, ConversationPointLifecycle
from .point_services import point_visible_to

_KIND_LABELS = {
    ConversationContextKind.DIRECT: "Conversation directe",
    ConversationContextKind.SPACE: "Espace",
    ConversationContextKind.GROUP: "Groupe",
    ConversationContextKind.ACTIVITY: "Activité",
    ConversationContextKind.OCCURRENCE: "Occurrence",
    ConversationContextKind.JOURNEY: "Démarche",
    ConversationContextKind.DOSSIER: "Dossier",
    ConversationContextKind.PROJECT: "Projet",
    ConversationContextKind.ACTION_PROPOSAL: "Proposition",
}
_POINT_KINDS = {
    ConversationPointKind.POLL: "poll",
    ConversationPointKind.CONFIRMATION: "confirmation",
    ConversationPointKind.FORM_REQUEST: "form",
    ConversationPointKind.EXCHANGE: "exchange",
}
_MEDIA_KINDS = {"voice", "audio", "image", "video", "file"}
_SIGNAL_ORDER = ("voice", "image", "video", "audio", "file", "poll", "form", "confirmation", "exchange")
_MAX_PREVIEW_CANDIDATES = 25


def _short_identity(conversation, context_label):
    """Keep the contextual subject, not the repeated bureaucratic prefix.

    The complete original Conversation title stays available in its N1 detail.
    This is a *presentation* of the existing title/context, not a rename.
    """
    label = (context_label or "").strip()
    override = (conversation.title_override or "").strip()
    if not label:
        return (override or "Conversation", "")
    if conversation.context.kind == ConversationContextKind.DIRECT:
        return (label, _KIND_LABELS[ConversationContextKind.DIRECT])
    # If an owner-authored override is genuinely distinct, preserve it.
    if override and label.casefold() not in override.casefold():
        return (override, label)
    for separator in (" — ", " – "):
        if separator in label:
            first, remainder = label.split(separator, 1)
            if first.strip() and remainder.strip():
                return (first.strip(), remainder.strip())
    return (label, _KIND_LABELS.get(conversation.context.kind, "Conversation"))


def _public_context_image(conversation):
    """Only use a public, published Event's existing cover via Discovery."""
    context = conversation.context
    activity = None
    occurrence = None
    if context.kind == ConversationContextKind.ACTIVITY:
        activity = context.activity
    elif context.kind == ConversationContextKind.OCCURRENCE:
        occurrence = context.occurrence
        activity = occurrence.activity
    if activity is None:
        return None
    if activity.visibility != ActivityVisibility.PUBLIC or activity.status != ActivityStatus.PUBLISHED:
        return None
    # A cover prepared for an unpublished event is not public media.
    from django.core.exceptions import ObjectDoesNotExist
    try:
        event = activity.event_vertical
    except (AttributeError, ObjectDoesNotExist):
        return None
    if not event.published_at:
        return None
    from discovery.representation import resolve_activity_representation
    presentation = resolve_activity_representation(activity=activity, occurrence=occurrence)
    if presentation.kind != "image" or not presentation.image_url:
        return None
    # Never turn an arbitrary remote URL into an unguarded image request.
    parsed = urlsplit(presentation.image_url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    return parsed.path


def _visible_candidates(profile, conversation, *, visibility_cache, audience_cache, history_cache):
    seen = set()
    for field in ("m9c_active_points", "m9c_resolved_points"):
        values = getattr(conversation, field, None)
        if values is None:
            continue
        for point in values:
            if point.pk in seen:
                continue
            seen.add(point.pk)
            if point.lifecycle == ConversationPointLifecycle.DRAFT:
                continue
            if not point_visible_to(
                profile, point, visibility_cache=visibility_cache,
                audience_cache=audience_cache, history_cache=history_cache,
            ):
                continue
            yield point


def _signals_and_preview(profile, conversation):
    """Only signals from Points and attachments the *current* viewer can read."""
    signal_set = set()
    preview = None
    preview_kind = None
    seen = 0
    # Per-call caches never survive a response and are never shared across
    # viewers. All decisions are computed by the canonical ACL services.
    visibility_cache = {}
    audience_cache = {}
    history_cache = {}
    manager_cache = {}
    candidates = _visible_candidates(
        profile, conversation, visibility_cache=visibility_cache,
        audience_cache=audience_cache, history_cache=history_cache,
    )
    for point in candidates:
        seen += 1
        if seen > _MAX_PREVIEW_CANDIDATES:
            break
        mapped_kind = _POINT_KINDS.get(point.kind)
        if mapped_kind:
            signal_set.add(mapped_kind)
        # Media kinds signal actual privately validated attachment objects;
        # never expose filename, URL, identity or a private thumbnail here.
        for attachment in point.attachments.all():
            if attachment.kind not in _MEDIA_KINDS:
                continue
            if can_download_attachment(
                profile, attachment, visibility_cache=visibility_cache,
                audience_cache=audience_cache, history_cache=history_cache,
                manager_cache=manager_cache,
            ):
                signal_set.add(attachment.kind)
        if preview is None:
            candidate = (point.title or point.body or "").strip()
            if candidate:
                preview = candidate
                preview_kind = mapped_kind or "point"
        if len(signal_set) == len(_SIGNAL_ORDER) and preview:
            break
    return {
        "media_kinds": [kind for kind in _SIGNAL_ORDER if kind in signal_set][:4],
        "point_preview": preview,
        "preview_kind": preview_kind,
    }


def conversation_list_card(profile, conversation, *, context_label, latest_result, attention_count):
    title, subtitle = _short_identity(conversation, context_label)
    signals = _signals_and_preview(profile, conversation)
    result = (latest_result or "").strip()
    preview = result or signals["point_preview"] or (conversation.purpose or "").strip()
    return {
        "title": title,
        "context_label": subtitle,
        "context_kind": conversation.context.kind,
        "context_image_url": _public_context_image(conversation),
        "preview": preview,
        "preview_kind": "result" if result else signals["preview_kind"] or "purpose",
        "media_kinds": signals["media_kinds"],
        "attention_count": attention_count,
    }
