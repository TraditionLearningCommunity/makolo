from __future__ import annotations

from dataclasses import dataclass

from .models import SpaceArchetype


@dataclass(frozen=True)
class SpaceProductConfig:
    """Presentation/capability configuration derived from a Space archetype.

    This layer never grants Permission, Mandate or Access. Authority remains
    exclusively in the authorization domain.
    """

    label: str
    navigation_section_label: str
    activities_label: str
    specialized_modules: frozenset[str]


SPACE_PRODUCT_CONFIGS = {
    SpaceArchetype.GENERIC: SpaceProductConfig(
        label="Espace générique",
        navigation_section_label="Activité",
        activities_label="Activités",
        specialized_modules=frozenset(),
    ),
    SpaceArchetype.CREATIVE: SpaceProductConfig(
        label="Artiste / création",
        navigation_section_label="Création",
        activities_label="Créations & activités",
        specialized_modules=frozenset(),
    ),
    SpaceArchetype.MEDIA: SpaceProductConfig(
        label="Média / journalisme",
        navigation_section_label="Production",
        activities_label="Productions & activités",
        specialized_modules=frozenset(),
    ),
    SpaceArchetype.EDUCATION: SpaceProductConfig(
        label="Enseignement / formation",
        navigation_section_label="Enseignement",
        activities_label="Programmes & activités",
        specialized_modules=frozenset(),
    ),
    SpaceArchetype.TRANSPORT_OPERATOR: SpaceProductConfig(
        label="Opérateur de transport",
        navigation_section_label="Offre de transport",
        activities_label="Services de transport",
        specialized_modules=frozenset({"transport"}),
    ),
}


def product_config_for_space(space) -> SpaceProductConfig:
    try:
        archetype = SpaceArchetype(space.archetype)
    except (ValueError, AttributeError):
        archetype = SpaceArchetype.GENERIC
    return SPACE_PRODUCT_CONFIGS[archetype]


def space_supports_specialized_module(space, module_key: str) -> bool:
    return module_key in product_config_for_space(space).specialized_modules