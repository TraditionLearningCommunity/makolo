from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import Http404
from rest_framework.exceptions import ValidationError

from .api.history_projection import build_personal_history_data
from .api.transverse_search_projection import build_profile_search


class PersonalSearchWebView(LoginRequiredMixin, TemplateView):
    template_name = "core/personal_transverse_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()[:120]
        try:
            page = max(1, int(self.request.GET.get("page", "1")))
        except ValueError:
            page = 1
        data = build_profile_search(
            profile=self.request.user, query=query,
            offset=(page - 1) * 24, limit=24,
        )
        selected_ref = (self.request.GET.get("selected") or "")[:120]
        selected = next(
            (
                item for item in data["items"]
                if f'{item["source"]["kind"]}:{item["source"]["id"]}' == selected_ref
            ),
            None,
        )
        context.update(
            search=data, q=query, page=page,
            selected_item=selected, selected_ref=selected_ref,
        )
        return context
