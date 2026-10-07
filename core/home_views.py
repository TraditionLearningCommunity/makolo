from types import SimpleNamespace

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from core.api.personal_projections import build_personal_now_projection


def _deadline_label(timing):
    state = (timing or {}).get("deadline_state")
    return {
        "overdue": "Échéance dépassée",
        "due_today": "Aujourd’hui",
    }.get(state, "")


def _display_value(value, *keys):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str):
            return candidate
    return ""


def _handoff_url(item):
    links = item.get("links") or {}
    direct = links.get("web") or links.get("detail")
    if direct:
        return direct
    for handoff in item.get("handoffs") or ():
        handoff_links = handoff.get("links") or {}
        target = (
            handoff.get("url")
            or handoff_links.get("web")
            or handoff_links.get("detail")
        )
        if target:
            return target
    return None


def _consequence_text(consequence):
    if isinstance(consequence, dict) and consequence.get("state") == "unknown":
        return ""
    return _display_value(consequence, "effect", "label")


def _web_now_item(item):
    response = item.get("response") or {}
    return SimpleNamespace(
        identity=item.get("id") or item["key"],
        context_label=item.get("human_context") or item.get("title") or "Makolo",
        source_label=item.get("owner_label") or "",
        action_label=response.get("label") or item.get("title") or "Ouvrir",
        summary=item.get("summary") or "",
        state=item.get("state_meaning") or "",
        why_now=_display_value(item.get("why_now"), "meaning"),
        consequence=_consequence_text(item.get("consequence")),
        turn=_display_value(item.get("turn"), "label", "type"),
        response_type=response.get("type") or "",
        url=_handoff_url(item),
        status_label="",
        deadline_label=_deadline_label(item.get("timing")),
        priority="",
        actionability=item.get("actionability") or "actionable",
        dimension=item.get("dimension"),
    )


def _now_web_context(data):
    projected = [_web_now_item(item) for item in data.get("items", [])]
    primary_attention = projected[0] if projected else None
    selection = data.get("selection") or {}
    freshness = data.get("freshness") or {}
    terminal = data.get("terminal") or {}
    continuation = data.get("continuation")
    continuation_state = (
        continuation.get("state") if isinstance(continuation, dict) else None
    )
    selection_state = selection.get("state") or "unknown"
    freshness_state = freshness.get("state") or "unknown"
    terminal_state = terminal.get("state") or "unknown"
    is_unavailable = (
        selection_state == "unavailable"
        or freshness_state == "unavailable"
        or terminal_state == "unavailable"
        or selection_state == "unknown"
    )
    is_calm = (
        data.get("actor_attention_state") == "calm"
        and selection_state == "empty"
        and terminal_state == "empty"
        and continuation_state in {None, "end", "END"}
    )
    return SimpleNamespace(
        primary_attention=primary_attention,
        primary_action=None,
        action_items=tuple(projected[1:]),
        knowledge_items=(),
        upcoming=(),
        all_clear=is_calm,
        is_calm=is_calm,
        is_partial=selection_state == "partial" or freshness_state == "partial",
        is_unavailable=is_unavailable,
        is_stale=freshness_state == "stale",
        terminal_message=terminal.get("message") or "",
        selection_reason=selection.get("reason") or "",
        continuation_state=continuation_state,
    )


class MatureParticipantHomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        observed_at = timezone.now()
        data = build_personal_now_projection(
            self.request.user,
            observed_at=observed_at,
        )
        context["home"] = _now_web_context(data)
        return context
