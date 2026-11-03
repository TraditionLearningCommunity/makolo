from __future__ import annotations

import uuid

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from intelligence.connection_web import connection_form_context, handle_connection_form
from intelligence.models import ProviderScope
from notifications.push import revoke_push_endpoint_by_id

from interoperability.catalog_presentation import connection_experience_context
from interoperability.presentation import present_connection
from interoperability.profile_projection import build_profile_interoperability_payload


class PersonalConnectionsView(LoginRequiredMixin, TemplateView):
    template_name = "core/personal_connections.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = build_profile_interoperability_payload(self.request.user)

        context.update(connection_form_context())
        context["interoperability"] = payload
        context["connections"] = [
            present_connection(row) for row in payload.get("connections", [])
        ]
        context.update(
            connection_experience_context(
                self.request,
                offers=context["connection_offers"],
                connections=context["connections"],
            )
        )
        context["connections_context_label"] = "Moi"
        context["connections_return_url"] = reverse("core:participant-me")
        context["connections_return_label"] = "Retour à Moi"
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
