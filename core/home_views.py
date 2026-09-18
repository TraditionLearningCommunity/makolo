from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from .home_presentation import MatureHomePresentation, build_mature_home


_NOW_ACTIONABILITIES = {"terminal", "blocking", "actionable"}


def _now_projection(home):
    """Keep Maintenant limited to facts that change a next step now.

    Waiting, advice and generic information remain available to their owner
    surfaces (notably En cours) but do not make the Home look busy.
    """
    ordered = []
    seen = set()
    for item in (
        home.primary_attention,
        home.primary_action,
        *home.action_items,
        *home.knowledge_items,
    ):
        if item is None or item.actionability not in _NOW_ACTIONABILITIES:
            continue
        if item.identity in seen:
            continue
        seen.add(item.identity)
        ordered.append(item)

    primary_attention = ordered[0] if ordered else None
    primary_action = next((item for item in ordered if item.actionability == "actionable"), None)
    primary_ids = {
        item.identity
        for item in (primary_attention, primary_action)
        if item is not None
    }
    remaining = tuple(item for item in ordered if item.identity not in primary_ids)

    return MatureHomePresentation(
        primary_attention=primary_attention,
        primary_action=primary_action,
        action_items=remaining,
        knowledge_items=(),
        upcoming=home.upcoming,
        all_clear=not ordered,
    )


class MatureParticipantHomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        home = build_mature_home(self.request.user, observed_at=timezone.now())
        context["home"] = _now_projection(home)
        return context
