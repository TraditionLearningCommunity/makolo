import uuid

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from intelligence.connection_web import connection_form_context, handle_connection_form
from intelligence.models import ProviderScope
from notifications.push import active_push_endpoints_for, revoke_push_endpoint_by_id

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
                "domain_integrations": payload.get("domain_integrations", []),
                "push_devices": [
                    {
                        "id": str(device.pk),
                        "platform": device.get_platform_display(),
                        "app_version": device.app_version,
                    }
                    for device in active_push_endpoints_for(self.request.user)[:30]
                ],
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("operation") == "revoke_push":
            try:
                endpoint_id = uuid.UUID(request.POST.get("endpoint_id", ""))
            except (ValueError, TypeError):
                raise Http404()
            if not revoke_push_endpoint_by_id(
                user=request.user, endpoint_id=endpoint_id,
            ):
                raise Http404()
            messages.success(request, "Cet appareil ne recevra plus les notifications push.")
            return redirect(reverse("core:participant-connections"))
        return handle_connection_form(request, scope=ProviderScope.PROFILE)

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response
