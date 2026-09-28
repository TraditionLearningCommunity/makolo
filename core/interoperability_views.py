from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from interoperability.profile_projection import build_profile_interoperability_payload


class PersonalConnectionsView(LoginRequiredMixin, TemplateView):
    template_name = "core/personal_connections.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = build_profile_interoperability_payload(self.request.user)

        context.update(
            {
                "interoperability": payload,
                "providers": payload.get("providers", []),
                "connections": payload.get("connections", []),
                "authorized_actions": [
                    action for action in payload.get("actions", []) if action.get("authorized")
                ],
                "extensions": [
                    extension
                    for extension in payload.get("extensions", [])
                    if extension.get("available") and extension.get("enabled")
                ],
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response
