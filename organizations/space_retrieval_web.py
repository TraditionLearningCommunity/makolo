from django.http import Http404
from django.views.generic import TemplateView

from .api.space_history_projection import build_space_history_projection
from .api.space_search_projection import build_space_search
from .space_web_views import SpaceWebMixin


class _SpaceRetrievalWebView(SpaceWebMixin):
    builder = None
    template_name = "organizations/space/retrieval.html"
    space_page_title = "Retrouver"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()[:120]
        try:
            page = max(1, int(self.request.GET.get("page", "1")))
        except ValueError:
            page = 1
        projection = self.builder(
            profile=self.request.user, space=self.space, query=query,
            responsibility_key=self.selected_responsibility["key"],
            offset=(page - 1) * 24, limit=24,
        )
        if projection is None:
            raise Http404
        selected_ref = (self.request.GET.get("selected") or "")[:120]
        selected = next(
            (
                item for item in projection["items"]
                if f'{item["source"]["kind"]}:{item["source"]["id"]}' == selected_ref
            ),
            None,
        )
        context.update(
            selected_item=selected, selected_ref=selected_ref,
            retrieval=projection, q=query, page=page,
            is_history=self.space_page_title == "Historique",
            route_name=self.route_name,
        )
        return context


class SpaceHistoryWebView(_SpaceRetrievalWebView):
    builder = staticmethod(build_space_history_projection)
    space_page_title = "Historique"
    route_name = "organizations:space-history"


class SpaceSearchWebView(_SpaceRetrievalWebView):
    builder = staticmethod(build_space_search)
    space_page_title = "Recherche"
    route_name = "organizations:space-search"
