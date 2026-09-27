from __future__ import annotations

from django.urls import reverse
from django.views.generic import TemplateView

from funding.models import FundingDetails
from funding.services import can_manage_funding

from .console_views import SpaceConsoleMixin


class SpaceConsoleCapabilityHubView(SpaceConsoleMixin, TemplateView):
    """Mature Space entry for an owner-backed capability reconciled by Z15."""

    template_name = "organizations/console/capability_hub.html"
    destination_name = None
    destination_scope = "slug"
    description = ""
    action_label = "Ouvrir les outils"

    def get_destination_url(self):
        if self.destination_scope == "space_id":
            kwargs = {"space_id": self.space.pk}
        else:
            kwargs = {"slug": self.space.slug}
        return reverse(self.destination_name, kwargs=kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module = self.space_console.workspace_module(self.module_key)
        context.update(
            {
                "capability_module": module,
                "capability_description": self.description,
                "capability_action_label": self.action_label,
                "capability_destination_url": self.get_destination_url(),
            }
        )
        return context


class SpaceConsoleFundingView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/funding.html"
    module_key = "funding"
    page_title = "Financements"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module = self.space_console.workspace_module("funding") or {"capabilities": []}
        candidates = (
            FundingDetails.objects.select_related("activity")
            .filter(activity__space=self.space)
            .order_by("-activity__created_at", "-id")
        )
        context["fundings"] = [
            funding for funding in candidates if can_manage_funding(self.request.user, funding)
        ]
        context["can_create_funding"] = "create" in module.get("capabilities", [])
        context["create_funding_url"] = f'{reverse("funding:create")}?space={self.space.slug}'
        return context
