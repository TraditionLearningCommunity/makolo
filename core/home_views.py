from types import SimpleNamespace
from uuid import UUID

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import NoReverseMatch, reverse
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


def _now_topology(item):
    """Only render owner-provided presentation semantics, never infer monitoring."""
    media = item.get("media_bindings") or ()
    if any(
        isinstance(binding, dict)
        and binding.get("authorized") is True
        and binding.get("resource_ref")
        and (
            binding.get("presentation_rank") == "primary"
            or binding.get("purpose") in {"understand", "establish", "act"}
        )
        for binding in media
    ):
        return "media"
    actions = item.get("business_actions") or ()
    if any(
        isinstance(action, dict)
        and action.get("capability")
        and action.get("label")
        and action.get("interaction_depth") in {"direct_now", "focused"}
        for action in actions
    ):
        return "action"
    members = item.get("relation_members") or ()
    relations = item.get("relations") or ()
    response = item.get("response") or {}
    member_ids = {
        member.get("id")
        for member in members
        if isinstance(member, dict) and isinstance(member.get("id"), str)
    }
    linked = any(
        isinstance(relation, dict)
        and isinstance(relation.get("kind"), str)
        and relation["kind"].strip()
        and len({
            value for value in (relation.get("member_ids") or ())
            if isinstance(value, str) and value in member_ids
        }) >= 2
        for relation in relations
        if isinstance(relation, dict)
        and isinstance(relation.get("member_ids"), (list, tuple))
    )
    if (
        len(member_ids) >= 2
        and linked
        and _display_value(item.get("why_now"), "meaning")
        and _consequence_text(item.get("consequence"))
        and response.get("type")
    ):
        return "composition"
    if response.get("type") in {"wait", "monitor", "waiting"}:
        return "waiting"
    return "meaning"


def _now_inline_media(item):
    """Expose only the first-party resource-view endpoint; never raw storage URLs."""
    allowed_prefix = "/api/v1/me/now/media/journey-artifacts/"
    result = []
    for binding in item.get("media_bindings") or ():
        if not isinstance(binding, dict) or binding.get("authorized") is not True:
            continue
        if not binding.get("resource_ref"):
            continue
        url = binding.get("url")
        if not isinstance(url, str) or not url.startswith(allowed_prefix):
            continue
        path, separator, query = url.partition("?")
        resource_id = path[len(allowed_prefix):].strip("/")
        if not resource_id or "/" in resource_id:
            continue
        from uuid import UUID

        try:
            UUID(resource_id)
        except (ValueError, AttributeError):
            continue
        if separator and query != "view=text":
            continue
        kind = binding.get("kind")
        if kind not in {"image", "pdf", "document", "audio", "video"}:
            continue
        original_url = binding.get("download_url")
        if not isinstance(original_url, str) or original_url != path:
            original_url = url
        result.append({
            "url": url,
            "download_url": original_url,
            "kind": kind,
            "label": binding.get("label") or "Média associé à la situation",
        })
        if len(result) == 3:
            break
    return tuple(result)


def _now_web_direct_actions(item):
    """Expose exact owner-issued form targets, never arbitrary POST links."""
    source = item.get("source") or {}
    if source.get("kind") != "recognition_redemption":
        return ()
    try:
        owner_id = UUID(str(source.get("id")))
    except (ValueError, AttributeError, TypeError):
        return ()

    forms = []
    for action in item.get("business_actions") or ():
        if not isinstance(action, dict):
            continue
        capability = action.get("capability")
        if (
            capability not in {"accept", "decline"}
            or action.get("interaction_depth") != "direct_now"
            or action.get("confirmation_required") is not True
        ):
            continue
        try:
            expected = reverse(
                "recognition_api:redemption-decision",
                kwargs={"redemption_id": owner_id, "decision": capability},
            )
        except NoReverseMatch:
            continue
        if action.get("href") != expected:
            continue
        forms.append({
            "url": expected,
            "label": "Accepter" if capability == "accept" else "Refuser",
            "owner_id": str(owner_id),
        })
    return tuple(forms)


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
        topology=_now_topology(item),
        horizon=_display_value(item.get("horizon"), "label", "text"),
        preparation=tuple(x for x in (item.get("makolo_preparation") or ()) if isinstance(x, str) and x.strip()),
        inline_media=_now_inline_media(item),
        direct_actions=_now_web_direct_actions(item),
        media_labels=tuple(
            binding.get("label") or "Média lié à la situation"
            for binding in (item.get("media_bindings") or ())
            if isinstance(binding, dict)
            and binding.get("authorized") is True
            and binding.get("resource_ref")
        ),
        relation_summaries=tuple(
            rel["summary"] for rel in (item.get("relations") or ())
            if isinstance(rel, dict) and isinstance(rel.get("summary"), str) and rel["summary"].strip()
        ),
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
