from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from intelligence.connection_web import connection_form_context, handle_connection_form
from intelligence.models import ProviderScope

from interoperability.presentation import (
    present_action,
    present_connection,
    present_extension,
    present_provider,
)
from interoperability.profile_projection import build_profile_interoperability_payload


class PersonalConnectionsView(LoginRequiredMixin, TemplateView):
    template_name = "core/personal_connections.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = build_profile_interoperability_payload(self.request.user)

        context.update(connection_form_context())
        context.update(
            {
                "interoperability": payload,
                "providers": [
                    present_provider(provider)
                    for provider in payload.get("providers", [])
                    if provider.get("available")
                ],
                "connections": [
                    present_connection(connection)
                    for connection in payload.get("connections", [])
                ],
                "authorized_actions": [
                    present_action(action)
                    for action in payload.get("actions", [])
                    if action.get("authorized")
                ],
                "extensions": [
                    present_extension(extension)
                    for extension in payload.get("extensions", [])
                    if extension.get("available") and extension.get("enabled")
                ],
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        return handle_connection_form(request, scope=ProviderScope.PROFILE)

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response
