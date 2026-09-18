from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class PersonalSurface:
    owner: str | None
    title: str
    back_url: str
    is_primary: bool


PRIMARY_ROUTES = {
    "core:participant-home": ("now", "Makolo"),
    "discovery:home": ("discover", "Découvrir"),
    "core:makolo-mark": ("mark", "Makolo"),
    "core:participant-ongoing": ("ongoing", "En cours"),
    "core:participant-me": ("me", "Moi"),
}

ONGOING_CORE_NAMES = {
    "participant-journeys",
    "participant-journey-detail",
    "participant-invitation-accept",
    "participant-invitation-decline",
    "participant-occurrence-live",
    "participant-accesses",
    "participant-access-detail",
}

PERSONAL_TICKET_NAMES = {
    "list",
    "detail",
    "order-detail",
    "order-create",
    "waitlist-list",
    "waitlist-join",
    "waitlist-leave",
    "waitlist-accept",
    "transfer-list",
    "transfer-create",
    "transfer-accept",
    "transfer-decline",
    "transfer-cancel",
}

DISCOVER_NAMESPACES = {"discovery", "events", "transport", "services", "opportunities", "funding"}
ME_NAMESPACES = {"personal_assets", "groups", "sharing"}
HEADER_NAMESPACES = {"account", "subscriptions", "organizations", "conversations", "notifications"}


def _reverse(name: str) -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def personal_surface_owner(request) -> PersonalSurface:
    match = getattr(request, "resolver_match", None)
    if match is None:
        return PersonalSurface(None, "Makolo", "", False)

    namespace = match.namespace or ""
    url_name = match.url_name or ""
    qualified = f"{namespace}:{url_name}" if namespace else url_name

    primary = PRIMARY_ROUTES.get(qualified)
    if primary:
        owner, title = primary
        return PersonalSurface(owner, title, "", True)

    if namespace in DISCOVER_NAMESPACES:
        return PersonalSurface("discover", "Découvrir", _reverse("discovery:home"), False)

    if namespace == "core" and url_name in ONGOING_CORE_NAMES:
        title = "Mes accès" if url_name in {"participant-accesses", "participant-access-detail"} else "En cours"
        return PersonalSurface("ongoing", title, _reverse("core:participant-ongoing"), False)

    if namespace == "core" and url_name == "participant-history":
        return PersonalSurface("me", "Historique", _reverse("core:participant-me"), False)

    if namespace == "objectives":
        return PersonalSurface("ongoing", "En cours", _reverse("core:participant-ongoing"), False)

    if namespace == "payments":
        return PersonalSurface("ongoing", "Paiement", _reverse("core:participant-ongoing"), False)

    if namespace == "tickets" and url_name in PERSONAL_TICKET_NAMES:
        if url_name == "waitlist-list":
            title = "Liste d’attente"
        elif url_name == "transfer-list":
            title = "Transferts"
        else:
            title = "En cours"
        return PersonalSurface("ongoing", title, _reverse("core:participant-ongoing"), False)

    if namespace in ME_NAMESPACES:
        titles = {
            "personal_assets": "Mes ressources",
            "groups": "Mes collectifs",
            "sharing": "Passeport Makolo",
        }
        return PersonalSurface("me", titles[namespace], _reverse("core:participant-me"), False)

    if namespace == "recognition" and url_name == "dashboard":
        return PersonalSurface("me", "Ce qui peut déjà vous aider", _reverse("core:participant-me"), False)

    if namespace == "loyalty" and url_name in {"dashboard", "portal"}:
        return PersonalSurface("me", "Mes avantages", _reverse("core:participant-me"), False)

    if namespace == "partners" and url_name == "my-detail":
        return PersonalSurface("me", "Ma relation partenaire", _reverse("core:participant-me"), False)

    if namespace == "goals":
        return PersonalSurface("me", "Anciennes mesures personnelles", _reverse("core:participant-me"), False)

    if namespace in HEADER_NAMESPACES:
        titles = {
            "account": "Compte",
            "subscriptions": "Abonnement",
            "organizations": "Agir comme",
            "conversations": "Conversations",
            "notifications": "Notifications",
        }
        back_url = _reverse("core:participant-home") if namespace in {"conversations", "notifications"} else ""
        return PersonalSurface("header", titles[namespace], back_url, False)

    return PersonalSurface(None, "Makolo", "", False)
