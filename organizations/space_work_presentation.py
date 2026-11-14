from __future__ import annotations

from dataclasses import dataclass

from .models import SpaceArchetype


@dataclass(frozen=True)
class SpaceWorkPresentationGrammar:
    """Human grammar over owner-backed Space Work facts."""

    surface_empty_message: str
    section_order: tuple[str, ...]
    labels: dict[str, str]
    empty_messages: dict[str, str]

    def label_for(self, key: str, fallback: str) -> str:
        return self.labels.get(key, fallback)

    def empty_message_for(self, key: str, label: str) -> str:
        return self.empty_messages.get(
            key,
            f"Aucun élément à afficher dans {label.lower()}.",
        )


_GENERIC_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune activité à afficher.",
    section_order=(
        "preparation",
        "upcoming",
        "active",
        "blocked",
        "activities",
        "completed",
        "offers",
        "routes",
        "vehicles",
        "requests",
    ),
    labels={
        "preparation": "À préparer",
        "upcoming": "À venir",
        "active": "En cours",
        "blocked": "Bloqués",
        "activities": "Toutes les activités",
        "completed": "Terminées",
        "offers": "Offres",
        "routes": "Routes",
        "vehicles": "Véhicules",
        "requests": "Demandes",
    },
    empty_messages={
        "preparation": "Rien à préparer.",
        "upcoming": "Rien à venir.",
        "active": "Rien en cours.",
        "blocked": "Aucun blocage à afficher.",
        "activities": "Aucune activité à afficher.",
        "completed": "Aucun élément terminé à afficher.",
        "offers": "Aucune offre à afficher.",
        "routes": "Aucune route à afficher.",
        "vehicles": "Aucun véhicule à afficher.",
        "requests": "Aucune demande à afficher.",
    },
)

_COMMUNITY_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune initiative à afficher.",
    section_order=(
        "preparation",
        "active",
        "upcoming",
        "blocked",
        "activities",
        "completed",
    ),
    labels={
        "preparation": "À préparer",
        "active": "En cours",
        "upcoming": "À venir",
        "blocked": "Bloquées",
        "activities": "Initiatives",
        "completed": "Historique",
    },
    empty_messages={
        "preparation": "Aucune initiative à préparer.",
        "active": "Aucune initiative en cours.",
        "upcoming": "Aucune action à venir.",
        "blocked": "Aucune initiative bloquée.",
        "activities": "Aucune initiative visible.",
        "completed": "Aucune initiative passée dans cette vue.",
    },
)

_CREATIVE_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune création à afficher.",
    section_order=(
        "preparation",
        "active",
        "upcoming",
        "blocked",
        "activities",
        "completed",
    ),
    labels={
        "preparation": "À préparer",
        "active": "En création",
        "upcoming": "À présenter",
        "blocked": "Bloquées",
        "activities": "Créations",
        "completed": "Historique",
    },
    empty_messages={
        "preparation": "Aucune création à préparer.",
        "active": "Aucune création en cours.",
        "upcoming": "Aucune présentation à venir.",
        "blocked": "Aucune création bloquée.",
        "activities": "Aucune création visible.",
        "completed": "Aucune création passée dans cette vue.",
    },
)

_MEDIA_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune production à afficher.",
    section_order=(
        "preparation",
        "active",
        "upcoming",
        "blocked",
        "activities",
        "completed",
    ),
    labels={
        "preparation": "À préparer",
        "active": "En production",
        "upcoming": "À venir",
        "blocked": "Bloquées",
        "activities": "Productions",
        "completed": "Historique",
    },
    empty_messages={
        "preparation": "Aucune production à préparer.",
        "active": "Aucune production en cours.",
        "upcoming": "Aucune réalisation à venir.",
        "blocked": "Aucune production bloquée.",
        "activities": "Aucune production visible.",
        "completed": "Aucune production passée dans cette vue.",
    },
)

_COMMERCE_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune offre ni commande à afficher.",
    section_order=(
        "preparation",
        "active",
        "blocked",
        "offers",
        "activities",
        "upcoming",
        "completed",
    ),
    labels={
        "preparation": "À traiter",
        "active": "Commandes actives",
        "blocked": "Bloquées",
        "offers": "Offres",
        "activities": "Ce que nous rendons disponible",
        "upcoming": "À venir",
        "completed": "Historique",
    },
    empty_messages={
        "preparation": "Aucune commande à traiter.",
        "active": "Aucune commande active.",
        "blocked": "Aucune commande bloquée.",
        "offers": "Aucune offre visible.",
        "activities": "Aucune disponibilité structurée visible.",
        "upcoming": "Aucune réalisation à venir.",
        "completed": "Aucun historique commercial dans cette vue.",
    },
)

_SERVICES_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune prestation ni demande à afficher.",
    section_order=(
        "requests",
        "preparation",
        "active",
        "blocked",
        "activities",
        "upcoming",
        "completed",
    ),
    labels={
        "requests": "Demandes à traiter",
        "preparation": "À préparer",
        "active": "Dossiers en cours",
        "blocked": "Dossiers bloqués",
        "activities": "Prestations",
        "upcoming": "À venir",
        "completed": "Terminés",
    },
    empty_messages={
        "requests": "Aucune demande à traiter.",
        "preparation": "Aucun dossier à préparer.",
        "active": "Aucun dossier en cours.",
        "blocked": "Aucun dossier bloqué.",
        "activities": "Aucune prestation visible.",
        "upcoming": "Aucune réalisation à venir.",
        "completed": "Aucun dossier terminé dans cette vue.",
    },
)

_PROGRAMMES_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucun programme ni session à afficher.",
    section_order=(
        "preparation",
        "requests",
        "active",
        "upcoming",
        "blocked",
        "activities",
        "completed",
    ),
    labels={
        "preparation": "À préparer",
        "requests": "Inscriptions à traiter",
        "active": "Sessions en cours",
        "upcoming": "Prochaines sessions",
        "blocked": "Bloqués",
        "activities": "Programmes",
        "completed": "Terminés",
    },
    empty_messages={
        "preparation": "Aucune session à préparer.",
        "requests": "Aucune inscription à traiter.",
        "active": "Aucune session en cours.",
        "upcoming": "Aucune prochaine session.",
        "blocked": "Aucun blocage à afficher.",
        "activities": "Aucun programme visible.",
        "completed": "Aucun élément terminé dans cette vue.",
    },
)

_TRANSPORT_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucun service, départ, itinéraire ou véhicule à afficher.",
    section_order=(
        "preparation",
        "active",
        "upcoming",
        "blocked",
        "activities",
        "routes",
        "vehicles",
        "completed",
    ),
    labels={
        "preparation": "À préparer",
        "active": "Départs en cours",
        "upcoming": "Prochains départs",
        "blocked": "Bloqués",
        "activities": "Services",
        "routes": "Routes",
        "vehicles": "Véhicules",
        "completed": "Terminés",
    },
    empty_messages={
        "preparation": "Aucun départ à préparer.",
        "active": "Aucun départ en cours.",
        "upcoming": "Aucun prochain départ.",
        "blocked": "Aucun départ bloqué.",
        "activities": "Aucun service visible.",
        "routes": "Aucune route visible.",
        "vehicles": "Aucun véhicule visible.",
        "completed": "Aucun départ terminé dans cette vue.",
    },
)

SPACE_WORK_PRESENTATION_GRAMMARS = {
    SpaceArchetype.GENERIC: _GENERIC_GRAMMAR,
    SpaceArchetype.COMMUNITY: _COMMUNITY_GRAMMAR,
    SpaceArchetype.CREATIVE: _CREATIVE_GRAMMAR,
    SpaceArchetype.MEDIA: _MEDIA_GRAMMAR,
    SpaceArchetype.COMMERCE: _COMMERCE_GRAMMAR,
    SpaceArchetype.EDUCATION: _PROGRAMMES_GRAMMAR,
    SpaceArchetype.SERVICE_PROVIDER: _SERVICES_GRAMMAR,
    SpaceArchetype.TRANSPORT_OPERATOR: _TRANSPORT_GRAMMAR,
}


def work_presentation_for_space(space) -> SpaceWorkPresentationGrammar:
    try:
        archetype = SpaceArchetype(space.archetype)
    except (ValueError, AttributeError):
        archetype = SpaceArchetype.GENERIC
    return SPACE_WORK_PRESENTATION_GRAMMARS.get(archetype, _GENERIC_GRAMMAR)


def ordered_work_section_keys(space, keys) -> tuple[str, ...]:
    grammar = work_presentation_for_space(space)
    available = tuple(dict.fromkeys(keys))
    ordered = [key for key in grammar.section_order if key in available]
    ordered.extend(key for key in available if key not in ordered)
    return tuple(ordered)
