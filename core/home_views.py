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


def _web_now_item(item):
    links = item.get("links") or {}
    return SimpleNamespace(
        identity=item["key"],
        context_label=item.get("human_context") or item.get("title") or "Makolo",
        source_label=item.get("owner_label") or "",
        action_label=item.get("title") or "Ouvrir",
        summary=item.get("summary") or "",
        url=links.get("web") or links.get("detail"),
        status_label="",
        deadline_label=_deadline_label(item.get("timing")),
        priority="",
        actionability=item.get("actionability") or "actionable",
        dimension=item.get("dimension"),
    )


def _now_web_context(data):
    projected = [_web_now_item(item) for item in data.get("items", [])]
    primary_attention = projected[0] if projected else None
    primary_action = next(
        (item for item in projected if item.dimension == "action"),
        None,
    )
    primary_ids = {
        item.identity
        for item in (primary_attention, primary_action)
        if item is not None
    }
    remaining = tuple(item for item in projected if item.identity not in primary_ids)
    return SimpleNamespace(
        primary_attention=primary_attention,
        primary_action=primary_action,
        action_items=remaining,
        knowledge_items=(),
        upcoming=(),
        all_clear=not projected,
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
