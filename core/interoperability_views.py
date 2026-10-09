from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from interoperability.profile_projection import build_profile_interoperability_payload


_CAPABILITY_LABELS = {
    "text_generate": "Génération de texte",
    "structured_generate": "Données structurées",
    "embed": "Représentation sémantique",
    "rerank": "Classement de résultats",
    "web_research": "Recherche sur le Web",
}


def _humanize_code(value, fallback):
    text = str(value or "").strip()
    if not text:
        return fallback
    text = " ".join(
        text.replace(".", " ").replace("_", " ").replace("-", " ").split()
    )
    return text[:1].upper() + text[1:] if text else fallback


def _capability_labels(connection):
    return [
        _CAPABILITY_LABELS.get(code, _humanize_code(code, "Capacité disponible"))
        for code in connection.get("capabilities", ())
    ]


def _connection_status_label(connection):
    if not connection.get("enabled") or connection.get("status") == "disabled":
        return "Désactivé"

    connected = bool(connection.get("connected"))
    health = connection.get("health")
    if health == "unavailable":
        return "Momentanément indisponible"
    if health == "degraded":
        return (
            "Connecté · disponibilité réduite"
            if connected
            else "Disponibilité réduite"
        )
    if health == "unknown":
        return "Connecté · état à vérifier" if connected else "État à vérifier"
    if connected and connection.get("usable"):
        return "Connecté et disponible"
    if connected:
        return "Connecté"
    if connection.get("available"):
        return "Disponible"
    return "État à vérifier"


def _present_connection(connection):
    return {
        **connection,
        "display_name": connection.get("display_name") or "Service",
        "status_label": _connection_status_label(connection),
        "capability_labels": _capability_labels(connection),
    }


def _present_provider(provider):
    return {
        **provider,
        "display_name": provider.get("display_name") or "Service disponible",
        "status_label": "Disponible" if provider.get("available") else "Indisponible",
        "capability_labels": [
            _CAPABILITY_LABELS.get(code, _humanize_code(code, "Capacité disponible"))
            for code in provider.get("capabilities", ())
        ],
    }


def _present_action(action):
    if action.get("available"):
        status_label = "Disponible"
    elif action.get("requires_connection"):
        status_label = "Connexion requise"
    else:
        status_label = "Indisponible pour le moment"
    return {
        **action,
        "display_name": action.get("display_name")
        or _humanize_code(action.get("code"), "Action"),
        "status_label": status_label,
    }


def _present_extension(extension):
    return {
        **extension,
        "display_name": extension.get("display_name")
        or _humanize_code(extension.get("code"), "Extension"),
    }


class PersonalConnectionsView(LoginRequiredMixin, TemplateView):
    template_name = "core/personal_connections.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = build_profile_interoperability_payload(self.request.user)

        context.update(
            {
                "interoperability": payload,
                "providers": [
                    _present_provider(provider)
                    for provider in payload.get("providers", [])
                    if provider.get("available")
                ],
                "connections": [
                    _present_connection(connection)
                    for connection in payload.get("connections", [])
                ],
                "authorized_actions": [
                    _present_action(action)
                    for action in payload.get("actions", [])
                    if action.get("authorized")
                ],
                "extensions": [
                    _present_extension(extension)
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
