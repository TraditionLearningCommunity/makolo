from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class PersonalSurface:
    owner: str | None
    title: str
    back_url: str
    is_primary: bool
    level: str = "contextual"
    family: str = ""


PRIMARY_ROUTES = {
    "core:participant-home": ("now", "Makolo"),
    "discovery:home": ("discover", "Découvrir"),
    "core:makolo-mark": ("mark", "Makolo"),
    "core:participant-ongoing": ("ongoing", "En cours"),
    "core:participant-me": ("me", "Moi"),
}

# Explicitly personal rendered destinations. Operator / staff / Space routes are
# intentionally absent even when they share a Django namespace.
ROUTES = {
    # Maintenant / action network.
    "social:my-solicitations": ("now", "Ce qui attend ma réponse", "n2", "Réseau d’action"),
    "social:solicitation-respond": ("now", "Répondre", "n4", "Réseau d’action"),
    "social:solicitation-cancel": ("now", "Annuler la proposition", "n4", "Réseau d’action"),
    "social:needs": ("now", "À la recherche de", "n2", "Réseau d’action"),
    "social:need-detail": ("now", "Besoin", "n3", "Réseau d’action"),
    "social:need-close": ("now", "Clore le besoin", "n4", "Réseau d’action"),
    "social:need-propose-self": ("now", "Proposer mon aide", "n4", "Réseau d’action"),

    # Découvrir.
    "discovery:activity-detail": ("discover", "Découvrir", "n3", "Possibilité"),
    "discovery:for-you": ("discover", "Pour vous", "n2", "Possibilités"),
    "groups:explore": ("discover", "Découvrir des collectifs", "n2", "Collectifs"),
    "opportunities:list": ("discover", "Opportunités", "n2", "Opportunités"),
    "opportunities:detail": ("discover", "Opportunité", "n3", "Opportunités"),
    "opportunities:submit": ("mark", "Proposer une opportunité", "n3", "Apport à Makolo"),
    "opportunities:submission-detail": ("mark", "Ma proposition", "n3", "Apport à Makolo"),
    "services:list": ("discover", "Services", "n2", "Services"),
    "services:start": ("discover", "Commencer", "n4", "Services"),
    "transport:search": ("discover", "Transport", "n2", "Transport"),
    "transport:departure-detail": ("discover", "Départ", "n3", "Transport"),
    "transport:book": ("discover", "Réserver", "n4", "Transport"),
    "events:list": ("discover", "Événements", "n2", "Événements"),
    "events:detail": ("discover", "Événement", "n3", "Événements"),
    "funding:detail": ("discover", "Financement", "n3", "Financement"),
    "funding:contribute": ("discover", "Contribuer", "n4", "Financement"),

    # En cours.
    "core:participant-journeys": ("ongoing", "Démarches", "n2", "Démarches"),
    "core:participant-journey-detail": ("ongoing", "Démarche", "n3", "Démarches"),
    "core:participant-invitation-accept": ("ongoing", "Accepter l’invitation", "n4", "Démarches"),
    "core:participant-invitation-decline": ("ongoing", "Refuser l’invitation", "n4", "Démarches"),
    "core:participant-occurrence-live": ("ongoing", "Jour J", "n3", "Occurrence"),
    "core:participant-accesses": ("ongoing", "Mes accès", "n2", "Accès"),
    "core:participant-access-detail": ("ongoing", "Accès", "n3", "Accès"),
    "objectives:dossier-list": ("ongoing", "Dossiers", "n2", "Dossiers"),
    "objectives:dossier-create": ("ongoing", "Nouveau Dossier", "n4", "Dossiers"),
    "objectives:dossier-detail": ("ongoing", "Dossier", "n3", "Dossiers"),
    "objectives:project-list": ("ongoing", "Projets", "n2", "Projets"),
    "objectives:project-create": ("ongoing", "Nouveau Projet", "n4", "Projets"),
    "objectives:project-detail": ("ongoing", "Projet", "n3", "Projets"),
    "tickets:list": ("ongoing", "Mes billets", "n2", "Billets"),
    "tickets:detail": ("ongoing", "Billet", "n3", "Billets"),
    "tickets:order-detail": ("ongoing", "Commande", "n3", "Billets"),
    "tickets:waitlist-list": ("ongoing", "Liste d’attente", "n2", "Liste d’attente"),
    "tickets:transfer-list": ("ongoing", "Transferts", "n2", "Transferts"),
    "payments:list": ("ongoing", "Paiements", "n3", "Paiements"),
    "payments:detail": ("ongoing", "Paiement", "n3", "Paiements"),
    "services:intake": ("ongoing", "Démarche", "n3", "Démarches"),
    "services:participant-trusted-reuse": ("ongoing", "Réutiliser une ressource", "n3", "Démarches"),
    "services:participant-artifact-upload": ("ongoing", "Ajouter un document", "n4", "Démarches"),
    "services:participant-artifact-version": ("ongoing", "Nouvelle version", "n4", "Démarches"),
    "services:participant-payment-evidence": ("ongoing", "Justifier un paiement", "n4", "Démarches"),

    # Moi / capital personnel.
    "core:participant-history": ("me", "Historique", "n2", "Historique"),
    "discovery:bookmarks": ("me", "Éléments gardés", "n2", "Éléments gardés"),
    "discovery:watch-list": ("me", "Veilles", "n2", "Veilles"),
    "discovery:watch-create": ("me", "Nouvelle Veille", "n4", "Veilles"),
    "discovery:watch-detail": ("me", "Veille", "n3", "Veilles"),
    "discovery:watch-edit": ("me", "Modifier la Veille", "n4", "Veilles"),
    "groups:list": ("me", "Mes collectifs", "n2", "Collectifs"),
    "groups:detail": ("me", "Collectif", "n3", "Collectifs"),
    "groups:members": ("me", "Membres", "n3", "Collectifs"),
    "groups:invitation": ("me", "Invitation", "n3", "Collectifs"),
    "personal_assets:list": ("me", "Mes ressources", "n2", "Ressources"),
    "personal_assets:detail": ("me", "Ressource", "n3", "Ressources"),
    "sharing:passport-me": ("me", "Passeport Makolo", "n2", "Passeport"),
    "sharing:inbound-create": ("me", "Importer", "n4", "Ressources"),
    "sharing:inbound-detail": ("me", "Import", "n3", "Ressources"),
    "sharing:delivery": ("me", "Partage reçu", "n3", "Partage"),
    "recognition:dashboard": ("me", "Reconnaissance", "n2", "Recognition"),
    "recognition:reward-use": ("me", "Utiliser un avantage", "n4", "Recognition"),
    "recognition:redemption-decision": ("me", "Décider", "n4", "Recognition"),
    "loyalty:dashboard": ("me", "Mes avantages", "n2", "Loyalty"),
    "loyalty:portal": ("me", "Relation avec l’organisation", "n3", "Loyalty"),
    "partners:my-detail": ("me", "Ma relation partenaire", "n2", "Partner"),
    "trust:my-proofs": ("me", "Mes preuves", "n3", "Ressources"),
    "goals:list": ("me", "Anciennes mesures personnelles", "legacy", "PersonalGoal"),

    # Header / compte.
    "conversations:list": ("header", "Conversations", "n2", "Conversations"),
    "conversations:detail": ("header", "Conversation", "n3", "Conversations"),
    "notifications:list": ("header", "Notifications", "n2", "Notifications"),
    "notifications:preferences": ("header", "Préférences de notification", "n3", "Notifications"),
    "account:profile": ("header", "Compte et paramètres", "n2", "Compte"),
    "account:interests": ("header", "Centres d’intérêt", "n3", "Compte"),
    "account:open-to": ("header", "Ouvert à", "n3", "Compte"),
    "account:switcher": ("header", "Changer de compte", "n2", "Compte"),
    "subscriptions:home": ("header", "Abonnement", "n2", "Abonnement"),
    "organizations:list": ("header", "Agir comme", "n2", "Contexte d’acteur"),
}

N4_PREFIXES = {
    "objectives:": {
        "project-link-dossier", "project-unlink-dossier", "project-lifecycle",
        "dossier-project", "dossier-assign", "dossier-unassign",
        "dossier-grant-authority", "dossier-revoke-authority",
        "dossier-link-journey", "dossier-unlink-journey",
        "dossier-add-dependency", "dossier-remove-dependency",
        "dossier-waive-dependency", "dossier-lifecycle",
    },
    "tickets:": {
        "order-create", "order-promotion", "order-cancel", "qr", "transfer-create",
        "waitlist-join", "waitlist-leave", "waitlist-accept",
        "transfer-accept", "transfer-decline", "transfer-cancel",
    },
    "payments:": {"start", "commerce-start", "obligation-start", "sandbox-complete", "manual-complete", "cancel"},
    "groups:": {
        "create", "edit", "join", "join-request", "join-request-cancel",
        "member-add", "member-suspend", "member-remove", "leave", "invite",
        "invitation-revoke", "import", "snapshot-create", "archive", "transfer",
        "responsibility", "activity-eligibility-request",
    },
    "personal_assets:": {"add", "add-version", "archive", "download", "use-in-journey", "save-artifact"},
    "sharing:": {"inbound-absorb", "inbound-discard", "journey-reuse", "delivery-go", "delivery-accept", "delivery-decline"},
    "conversations:": {"invitation-respond", "point-respond", "point-acknowledge", "point-exchange", "attachment"},
    "notifications:": {"open", "mark-read", "read-all"},
    "subscriptions:": {"preview", "change", "addon-remove-preview", "addon-remove", "transition-cancel", "transition-complete"},
    "account:": {"password-change", "delete", "interest-quick-capture", "interest-prompt-dismiss", "switch-account", "remove-account", "add-account"},
}


def _reverse(name: str) -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def _back(owner: str) -> str:
    return {
        "now": _reverse("core:participant-home"),
        "discover": _reverse("discovery:home"),
        "mark": _reverse("core:makolo-mark"),
        "ongoing": _reverse("core:participant-ongoing"),
        "me": _reverse("core:participant-me"),
    }.get(owner, "")


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
        return PersonalSurface(owner, title, "", True, "n1", title)

    route = ROUTES.get(qualified)
    if route:
        owner, title, level, family = route
        return PersonalSurface(owner, title, _back(owner), False, level, family)

    for prefix, names in N4_PREFIXES.items():
        if qualified.startswith(prefix) and url_name in names:
            owner = {
                "objectives:": "ongoing",
                "tickets:": "ongoing",
                "payments:": "ongoing",
                "groups:": "me",
                "personal_assets:": "me",
                "sharing:": "me",
                "conversations:": "header",
                "notifications:": "header",
                "subscriptions:": "header",
                "account:": "header",
            }[prefix]
            return PersonalSurface(owner, "Makolo", _back(owner), False, "n4", "")

    # A missing entry is intentional: no whole namespace is silently absorbed
    # into the personal shell. Space/operator/staff/public surfaces remain
    # unowned until their own context explicitly claims them.
    return PersonalSurface(None, "Makolo", "", False)
