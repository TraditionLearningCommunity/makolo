from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from .api.space_attention_projection import (
    build_space_discover_projection,
    build_space_now_projection,
)
from .api.workspace_projection import build_space_workspace, workspace_spaces

logger = logging.getLogger(__name__)


def space_projection_ui_state(projection):
    """Map an owner-backed projection to a presentation state without inventing facts."""
    if not isinstance(projection, dict):
        return "error"

    items = projection.get("items")
    selection = projection.get("selection")
    if not isinstance(items, list) or not isinstance(selection, dict):
        return "error"

    selection_state = selection.get("state")
    if items:
        return "partial" if selection_state == "partial" else "content"
    if selection_state in {"unavailable", "empty", "partial", "error"}:
        return selection_state
    return "error"


class SpaceWebMixin(LoginRequiredMixin, TemplateView):
    """Space Web shell backed only by current ZS projections."""

    login_url = "core:login"
    space_nav_key = "now"
    space_page_title = "Maintenant"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

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

    def _space_nav_url(self, name):
        url = self._space_url(name)
        key = self.selected_responsibility["key"]
        if key == "all":
            return url
        return f"{url}?{urlencode({'responsibility': key})}"

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
                "space_root_url": self._space_nav_url("organizations:console-entry"),
                "space_discover_url": self._space_nav_url("organizations:space-discover"),
                "space_work_url": self._space_nav_url("organizations:space-work"),
                "space_us_url": self._space_nav_url("organizations:space-us"),
                "space_mark_url": self._space_nav_url("organizations:space-mark"),
                "space_console_url": self._space_url("organizations:console-overview"),
            }
        )
        return context


class SpaceProjectionViewMixin(SpaceWebMixin):
    """Render one ZS projection while preserving unavailable/empty/error semantics."""

    projection_builder = None

    def projection_kwargs(self):
        return {
            "profile": self.request.user,
            "space": self.space,
            "responsibility_key": self.selected_responsibility["key"],
        }

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            projection = self.projection_builder(**self.projection_kwargs())
        except Exception:
            logger.exception(
                "Space projection failed",
                extra={
                    "space_slug": self.space.slug,
                    "surface": self.space_nav_key,
                },
            )
            context["projection"] = {
                "selection": {"state": "error"},
                "items": [],
                "has_more": False,
            }
            context["projection_state"] = "error"
            return self.render_to_response(context, status=503)

        if projection is None:
            raise Http404

        context["projection"] = projection
        context["projection_state"] = space_projection_ui_state(projection)
        status = 503 if context["projection_state"] == "error" else 200
        return self.render_to_response(context, status=status)


class SpaceNowView(SpaceProjectionViewMixin):
    template_name = "organizations/space/now.html"
    space_nav_key = "now"
    space_page_title = "Maintenant"
    projection_builder = staticmethod(build_space_now_projection)


class SpaceDiscoverView(SpaceProjectionViewMixin):
    template_name = "organizations/space/discover.html"
    space_nav_key = "discover"
    space_page_title = "Découvrir"
    projection_builder = staticmethod(build_space_discover_projection)


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
