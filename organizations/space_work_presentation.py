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
            f"Aucun élément visible dans {label.lower()} pour le moment.",
        )


_GENERIC_GRAMMAR = SpaceWorkPresentationGrammar(
    surface_empty_message="Aucune activité visible pour le moment.",
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
        "preparation": "Rien à préparer pour le moment.",
        "upcoming": "Rien à venir pour le moment.",
        "active": "Rien en cours pour le moment.",
        "blocked": "Aucun blocage projeté pour le moment.",
        "activities": "Aucune activité visible pour le moment.",
        "completed": "Rien de terminé dans cette vue pour le moment.",
        "offers": "Aucune offre visible pour le moment.",
        "routes": "Aucune route visible pour le moment.",
        "vehicles": "Aucun véhicule visible pour le moment.",
        "requests": "Aucune demande visible pour le moment.",
    },
)

SPACE_WORK_PRESENTATION_GRAMMARS = {
    SpaceArchetype.GENERIC: _GENERIC_GRAMMAR,
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
