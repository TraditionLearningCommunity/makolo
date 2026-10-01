from __future__ import annotations

from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from .api.space_attention_projection import (
    build_space_discover_projection,
    build_space_now_projection,
)
from .api.workspace_projection import build_space_workspace, workspace_spaces


class SpaceWebMixin(TemplateView):
    """WS1 Space Web shell backed only by current ZS projections."""

    space_nav_key = "now"
    space_page_title = "Maintenant"

    def dispatch(self, request, *args, **kwargs):
        self.space = workspace_spaces(request.user).filter(slug=kwargs["slug"]).first()
        if self.space is None:
            raise Http404

        self.workspace = build_space_workspace(request.user, self.space)
        if self.workspace is None:
            raise Http404

        responsibilities = tuple(self.workspace.get("responsibilities") or ())
        requested_key = (request.GET.get("responsibility") or "all").strip()
        selected = next(
            (row for row in responsibilities if row.get("key") == requested_key),
            None,
        )
        if selected is None:
            raise Http404

        self.responsibilities = responsibilities
        self.selected_responsibility = selected
        return super().dispatch(request, *args, **kwargs)

    def _space_url(self, name):
        return reverse(name, kwargs={"slug": self.space.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business_label = (
            self.workspace.get("operating_preset", {}).get("primary_business_label")
            or "Métier"
        )
        switcher_items = tuple(
            {
                "name": candidate.name,
                "slug": candidate.slug,
                "url": reverse(
                    "organizations:console-entry",
                    kwargs={"slug": candidate.slug},
                ),
            }
            for candidate in workspace_spaces(self.request.user)
        )
        context.update(
            {
                "space": self.space,
                "organization": self.space,
                "space_web": True,
                "space_context": True,
                "space_workspace": self.workspace,
                "space_nav_key": self.space_nav_key,
                "space_page_title": self.space_page_title,
                "space_business_label": business_label,
                "space_responsibilities": self.responsibilities,
                "selected_responsibility": self.selected_responsibility,
                "space_switcher_items": switcher_items,
                "space_root_url": self._space_url("organizations:console-entry"),
                "space_discover_url": self._space_url("organizations:space-discover"),
                "space_work_url": self._space_url("organizations:space-work"),
                "space_us_url": self._space_url("organizations:space-us"),
                "space_mark_url": self._space_url("organizations:space-mark"),
                "space_console_url": self._space_url("organizations:console-overview"),
            }
        )
        return context


class SpaceNowView(SpaceWebMixin):
    template_name = "organizations/space/now.html"
    space_nav_key = "now"
    space_page_title = "Maintenant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projection"] = build_space_now_projection(
            profile=self.request.user,
            space=self.space,
            responsibility_key=self.selected_responsibility["key"],
        )
        return context


class SpaceDiscoverView(SpaceWebMixin):
    template_name = "organizations/space/discover.html"
    space_nav_key = "discover"
    space_page_title = "Découvrir"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projection"] = build_space_discover_projection(
            profile=self.request.user,
            space=self.space,
        )
        return context


class SpaceWorkView(SpaceWebMixin):
    template_name = "organizations/space/work.html"
    space_nav_key = "work"

    @property
    def space_page_title(self):
        return (
            self.workspace.get("operating_preset", {}).get("primary_business_label")
            or "Métier"
        )


class SpaceUsView(SpaceWebMixin):
    template_name = "organizations/space/us.html"
    space_nav_key = "us"
    space_page_title = "Nous"


class SpaceMarkView(SpaceWebMixin):
    template_name = "organizations/space/mark.html"
    space_nav_key = "mark"
    space_page_title = "Makolo Mark"
