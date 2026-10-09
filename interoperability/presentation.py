from __future__ import annotations

from typing import Any


CAPABILITY_LABELS = {
    "text_generate": "Génération de texte",
    "structured_generate": "Données structurées",
    "embed": "Représentation sémantique",
    "rerank": "Classement de résultats",
    "web_research": "Recherche sur le Web",
}


def humanize_code(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = " ".join(
        text.replace(".", " ").replace("_", " ").replace("-", " ").split()
    )
    return text[:1].upper() + text[1:] if text else fallback


def capability_label(value: object) -> str:
    code = str(value or "").strip()
    return CAPABILITY_LABELS.get(
        code,
        humanize_code(code, "Capacité disponible"),
    )


def connection_status_label(connection: dict[str, Any]) -> str:
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


def present_connection(connection: dict[str, Any]) -> dict[str, Any]:
    return {
        **connection,
        "display_name": connection.get("display_name") or "Service",
        "status_label": connection_status_label(connection),
        "capability_labels": [
            capability_label(code) for code in connection.get("capabilities", ())
        ],
    }


def present_provider(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        **provider,
        "display_name": provider.get("display_name") or "Service disponible",
        "status_label": "Disponible" if provider.get("available") else "Indisponible",
        "capability_labels": [
            capability_label(code) for code in provider.get("capabilities", ())
        ],
    }


def present_action(action: dict[str, Any]) -> dict[str, Any]:
    if action.get("available"):
        status_label = "Disponible"
    elif action.get("requires_connection"):
        status_label = "Connexion requise"
    else:
        status_label = "Indisponible pour le moment"
    return {
        **action,
        "display_name": action.get("display_name")
        or humanize_code(action.get("code"), "Action"),
        "status_label": status_label,
    }


def present_extension(extension: dict[str, Any]) -> dict[str, Any]:
    return {
        **extension,
        "display_name": extension.get("display_name")
        or humanize_code(extension.get("code"), "Extension"),
    }
