from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from discovery.views import DiscoveryHomeView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from intelligence.interoperability import project_provider_connection, provider_connections_for_space
from intelligence.connection_web import connection_form_context, handle_connection_form
from intelligence.models import ProviderScope

from interoperability.catalog_presentation import connection_experience_context
from interoperability.presentation import present_connection
from interoperability.projections import build_interoperability_payload
from interoperability.domain_integrations import space_domain_integrations

from .api.space_attention_projection import (
    build_space_discover_projection,
    build_space_now_projection,
)
from .api.space_pilot_projection import build_space_pilot_projection
from .api.space_relationships_projection import build_space_relationships_projection
from .api.space_us_projection import build_space_us_projection
from .api.space_us_resources_projection import build_space_us_resources_projection
from .api.space_us_authority import build_space_us_authority
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
                "space_relationships_url": self._space_nav_url(
                    "organizations:space-relationships"
                ),
                "space_pilot_url": self._space_nav_url("organizations:space-pilot"),
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


class SpaceDiscoverView(SpaceWebMixin, DiscoveryHomeView):
    """Use the existing Discovery Web field with verified Space context."""

    template_name = "discovery/home.html"
    space_nav_key = "discover"
    space_page_title = "Découvrir"


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

    def get_template_names(self):
        if self.request.GET.get("detail") == "authority":
            return ["organizations/space/us_authority.html"]
        if self.request.GET.get("detail") == "resources":
            return ["organizations/space/us_resources.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.GET.get("detail") == "resources":
            kind = self.request.GET.get("kind") or "document"
            try:
                offset = int(self.request.GET.get("offset", "0"))
                resources = build_space_us_resources_projection(
                    profile=self.request.user, space=self.space,
                    kind=kind, offset=offset,
                )
            except (ValueError, TypeError) as exc:
                raise Http404 from exc
            if resources is None:
                raise Http404
            root_url = self._space_nav_url("organizations:space-us")
            separator = "&" if "?" in root_url else "?"
            context["resources_depth"] = resources
            context["resources_back_url"] = root_url
            context["resources_base_url"] = f"{root_url}{separator}detail=resources"
            context["resources_passport_url"] = self._space_url(
                "sharing:passport-space-history"
            )
            context["resources_presentation_url"] = self._space_url(
                "presentations:space-library"
            )
            context["resources_documents_url"] = self._space_url(
                "organizations:space-documents"
            )
            return context
        if self.request.GET.get("detail") == "authority":
            authority = build_space_us_authority(
                profile=self.request.user, space=self.space
            )
            if authority is None:
                raise Http404
            requested_key = (self.request.GET.get("mandate") or "").strip()
            mandates = authority["mandates"]
            if requested_key:
                mandates = [row for row in mandates if row["key"] == requested_key]
                if not mandates:
                    raise Http404
            context["authority_mandates"] = mandates
            return context
        try:
            projection = build_space_us_projection(
                profile=self.request.user,
                space=self.space,
            )
        except Exception:
            logger.exception(
                "Space Nous projection failed",
                extra={"space_slug": self.space.slug},
            )
            context["projection"] = None
            context["us_projection_error"] = True
            context["us_owner_links"] = {}
            return context
        owner_links = {
            "authority": f'{self._space_url("organizations:space-us")}?detail=authority',
            "relationships": context["space_relationships_url"]
            if projection.get("handoffs", {}).get("relationships")
            else None,
        }
        capabilities = projection.get("capabilities", {})
        if capabilities.get("manage_team"):
            owner_links["team"] = self._space_url("organizations:console-team")
        if capabilities.get("manage_ownership"):
            owner_links["ownership"] = self._space_url("organizations:console-team")
        if projection.get("links", {}).get("trust"):
            owner_links["trust"] = self._space_url("organizations:console-trust")
        if projection.get("resources", {}).get("visibility") == "visible":
            us_url = self._space_nav_url("organizations:space-us")
            separator = "&" if "?" in us_url else "?"
            owner_links["resources"] = f"{us_url}{separator}detail=resources"
        if capabilities.get("update_space"):
            owner_links["settings"] = self._space_url("organizations:console-settings")
            owner_links["passport"] = self._space_url("sharing:passport-space")
        if any(
            module.get("key") == "analytics"
            for module in self.workspace.get("modules", ())
        ):
            owner_links["pilot"] = context["space_pilot_url"]
        if has_direct_space_permission(
            self.request.user, self.space, PermissionCode.SPACE_MANAGE
        ):
            owner_links["connections"] = self._space_url(
                "organizations:space-interoperability"
            )

        context["projection"] = projection
        context["us_owner_links"] = owner_links
        context["us_work_base_url"] = self._space_url("organizations:space-work")
        return context


    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceInteroperabilityView(SpaceWebMixin):
    template_name = "organizations/space/interoperability.html"
    space_nav_key = "us"
    space_page_title = "Connexions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not has_direct_space_permission(
            self.request.user, self.space, PermissionCode.SPACE_MANAGE
        ):
            raise Http404

        connections = [
            project_provider_connection(connection, manageable=True)
            for connection in provider_connections_for_space(self.space)
        ]
        context["interoperability"] = build_interoperability_payload(
            context="space",
            connections=connections,
            self_link=(
                f"/api/v1/organizations/workspaces/{self.space.slug}/"
                "interoperability/"
            ),
            actor=self.request.user,
            authority_context=self.space,
            domain_integrations=space_domain_integrations(self.request.user, self.space),
        )
        context["domain_integrations"] = context["interoperability"]["domain_integrations"]
        context.update(connection_form_context())
        context["connections"] = [present_connection(row) for row in connections]
        context.update(
            connection_experience_context(
                self.request,
                offers=context["connection_offers"],
                connections=context["connections"],
            )
        )
        context["connections_context_label"] = "Nous"
        context["connections_return_url"] = context["space_us_url"]
        context["connections_return_label"] = "Retour à Nous"
        return context
    def post(self, request, *args, **kwargs):
        if not has_direct_space_permission(
            request.user, self.space, PermissionCode.SPACE_MANAGE,
        ):
            raise Http404
        return handle_connection_form(
            request, scope=ProviderScope.SPACE, space=self.space,
        )



    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceRelationshipsView(SpaceWebMixin):
    template_name = "organizations/space/relationships.html"
    space_nav_key = "us"
    space_page_title = "Personnes & relations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projection = build_space_relationships_projection(
            profile=self.request.user,
            space=self.space,
            query=self.request.GET.get("q", "")[:120],
            relation_kind=self.request.GET.get("kind", "")[:40],
            relation_id=self.request.GET.get("id", "")[:80],
        )
        sections = projection.get("sections", {})
        owner_links = {}
        route_by_section = {
            "team": "organizations:console-team",
            "groups": "organizations:console-groups",
            "crm_contacts": "organizations:console-crm",
            "audiences": "organizations:console-audiences",
            "partners": "organizations:console-partners",
        }
        for section_key, route_name in route_by_section.items():
            if section_key in sections:
                owner_links[section_key] = self._space_url(route_name)

        context["projection"] = projection
        context["relationship_owner_links"] = owner_links
        context["space_page_title"] = projection.get("label") or self.space_page_title
        return context


    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class SpacePilotView(SpaceWebMixin):
    template_name = "organizations/space/pilot.html"
    space_nav_key = "us"
    space_page_title = "Piloter"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projection = build_space_pilot_projection(
            profile=self.request.user,
            space=self.space,
        )
        context["projection"] = projection
        context["pilot_owner_links"] = (
            {"analytics": self._space_url("organizations:console-analytics")}
            if "analytics" in projection.get("sections", {})
            else {}
        )
        return context


class SpaceMarkView(SpaceWebMixin):
    template_name = "organizations/space/mark.html"
    space_nav_key = "mark"
    space_page_title = "Makolo Mark"
