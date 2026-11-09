"""Chronological Conversation timeline: current Point truth, compact readable past.

A completed group is only a *presentation* over adjacent, authorized Points.
No Point, answer, media, resolution or domain-event is moved or copied.
Pagination delegates to C5's signed, profile-scoped history cursor.
"""
from django.utils import timezone

from .form_services import form_request_completed_for_profile
from .history import page_points_for_profile
from .point_interactions import point_interactions_for_profile
from .point_models import ConversationPointKind, ConversationPointLifecycle
from .point_services import point_resolution_visible_to

TERMINAL_LIFECYCLES = {
    ConversationPointLifecycle.RESOLVED,
    ConversationPointLifecycle.EXPIRED,
    ConversationPointLifecycle.CANCELLED,
    ConversationPointLifecycle.SUPERSEDED,
}


def timeline_presentation(profile, point, *, interactions=None):
    """Minimal, authorized state used by both Flutter and Web.

    A response-closed Point still requiring the viewer's management decision
    remains expanded. An open Point answered by this Profile may be folded,
    but always remains accessible to expand and revise if permitted.
    """
    actions = interactions if interactions is not None else point_interactions_for_profile(
        profile, point,
    )
    lifecycle = point.lifecycle
    if point.shared_pinned_at and lifecycle not in TERMINAL_LIFECYCLES:
        return {"compact": False, "summary": ""}
    if lifecycle in TERMINAL_LIFECYCLES:
        compact = True
    elif actions["can_resolve"] or actions["can_close_responses"] or actions["can_acknowledge"]:
        compact = False
    elif point.kind == ConversationPointKind.FORM_REQUEST:
        compact = form_request_completed_for_profile(point, profile)
    elif actions["my_response"] is not None and point.kind != ConversationPointKind.EXCHANGE:
        compact = True
    elif lifecycle == ConversationPointLifecycle.RESPONSE_CLOSED:
        compact = True
    elif (
        point.kind == ConversationPointKind.INFORMATION
        and point.requires_acknowledgement and actions["acknowledged"]
    ):
        compact = True
    else:
        compact = False

    if not compact:
        return {"compact": False, "summary": ""}

    if lifecycle == ConversationPointLifecycle.RESOLVED:
        if point_resolution_visible_to(profile, point):
            try:
                summary = point.resolution.summary or "Point résolu"
            except (AttributeError, point.resolution.RelatedObjectDoesNotExist):
                summary = "Point résolu"
        else:
            summary = "Point résolu"
    elif lifecycle == ConversationPointLifecycle.SUPERSEDED:
        summary = "Point remplacé"
    elif lifecycle == ConversationPointLifecycle.CANCELLED:
        summary = "Point annulé"
    elif lifecycle == ConversationPointLifecycle.EXPIRED:
        summary = "Point expiré"
    elif point.kind == ConversationPointKind.FORM_REQUEST:
        summary = "Formulaire terminé"
    elif actions["my_response"] is not None:
        summary = "Réponse enregistrée"
    elif actions["acknowledged"]:
        summary = "Prise de connaissance enregistrée"
    else:
        summary = "Réponses closes"

    return {"compact": True, "summary": summary[:160]}


def recent_timeline_for_profile(profile, conversation, *, limit=40):
    """Newest authorized window, then in chronological order for display."""
    page = page_points_for_profile(profile, conversation, section="all", limit=limit)
    return {
        "points": list(reversed(page["results"])),
        "next_cursor": page["next_cursor"],
    }


def group_timeline_points(profile, points, *, focus_id=None):
    """Group *adjacent* completed Points on the same local day.

    Never reorder noncompleted Points to keep a neat archive. A group remains
    precisely in its historical position, and a focused Point opens its group.
    """
    groups = []
    current = None
    for point in points:
        day = timezone.localtime(point.published_at).date() if point.published_at else None
        state = timeline_presentation(profile, point)
        if state["compact"]:
            if current and current["kind"] == "completed" and current["day"] == day:
                current["points"].append({
                    "point": point, "summary": state["summary"],
                })
                current["focus"] = current["focus"] or str(point.pk) == str(focus_id)
                continue
            current = {
                "kind": "completed", "day": day, "points": [
                    {"point": point, "summary": state["summary"]},
                ], "focus": str(point.pk) == str(focus_id),
            }
        else:
            current = {"kind": "point", "day": day, "point": point}
        groups.append(current)
    return groups
