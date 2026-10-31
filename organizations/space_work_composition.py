"""Derived Métier reading perspectives; no owner truth or authority duplication."""
from __future__ import annotations

from organizations.models import SpaceArchetype


# Reading groups do not replace owner-backed Business Sections.
_GRAMMARS = {
    SpaceArchetype.GENERIC: (
        ("continuity", "Ce qui se prépare et continue",
         ("preparation", "upcoming", "active", "requests", "blocked")),
        ("portfolio", "Nos activités", ("activities",)),
        ("specialized", "Autres réalités opérées",
         ("offers", "routes", "vehicles")),
        ("history", "Déjà réalisé", ("completed",)),
    ),
    SpaceArchetype.COMMUNITY: (
        ("continuity", "Ce que nous faisons avancer",
         ("preparation", "active", "upcoming", "blocked", "requests")),
        ("portfolio", "Nos initiatives", ("activities",)),
        ("specialized", "Autres actions réelles",
         ("offers", "routes", "vehicles")),
        ("history", "Actions passées", ("completed",)),
    ),
    # Programmes are durable Activities; Sessions are Occurrences.
    SpaceArchetype.EDUCATION: (
        ("portfolio", "Nos programmes", ("activities",)),
        ("sessions", "Sessions et préparation",
         ("upcoming", "active", "preparation")),
        ("registrations", "Inscriptions et démarches",
         ("requests", "blocked")),
        ("specialized", "Autres activités réelles",
         ("offers", "routes", "vehicles")),
        ("history", "Parcours et sessions passés", ("completed",)),
    ),
    # Prestations offered != engaged Service Journey cases.
    SpaceArchetype.SERVICE_PROVIDER: (
        ("requests", "Demandes à examiner", ("requests",)),
        ("cases", "Dossiers à accompagner",
         ("preparation", "active", "blocked")),
        ("portfolio", "Prestations proposées", ("activities",)),
        ("occurrences", "Rendez-vous et réalisations", ("upcoming",)),
        ("specialized", "Autres réalités opérées",
         ("offers", "routes", "vehicles")),
        ("history", "Prestations passées", ("completed",)),
    ),
}
_QUESTIONS = {
    SpaceArchetype.GENERIC: (
        "Qu’est-ce que nous faisons réellement, qu’est-ce qui se prépare "
        "et qu’est-ce qui continue ?"
    ),
    SpaceArchetype.COMMUNITY: (
        "Qu’est-ce que nous faisons concrètement avancer ensemble, "
        "sur le terrain ou dans la durée ?"
    ),
    SpaceArchetype.EDUCATION: (
        "Quels programmes faisons-nous vivre, quelles sessions préparons-nous "
        "et où en sont les inscriptions et conditions nécessaires ?"
    ),
    SpaceArchetype.SERVICE_PROVIDER: (
        "Quelles prestations proposons-nous, quelles demandes traiter et "
        "quels dossiers accompagner jusqu’au résultat ?"
    ),
}
_CALM = {
    SpaceArchetype.GENERIC: (
        "Aucune activité ne demande de préparation ou de conduite "
        "dans cette vue. Le travail durable reste accessible ci-dessous."
    ),
    SpaceArchetype.COMMUNITY: (
        "Rien ne demande d’intervention dans cette vue. "
        "Les initiatives portées par le collectif restent accessibles."
    ),
    SpaceArchetype.EDUCATION: (
        "Aucune session ni inscription ne demande d’intervention dans cette "
        "vue. Les programmes restent accessibles."
    ),
    SpaceArchetype.SERVICE_PROVIDER: (
        "Aucune demande ni dossier ne demande d’intervention dans cette vue. "
        "Les prestations proposées restent accessibles."
    ),
}


def compose_space_work_business_world(*, archetype, label, sections, limited, is_root=True):
    """Organize only real and authorized entries; no rankings or state copies.

    A reading group exists when its underlying owner section has real rows or
    a server continuation. Unknown domain sections remain discoverable.
    """
    if archetype not in _GRAMMARS:
        return None

    chapters = []
    seen = set()
    for key, title, keys in _GRAMMARS[archetype]:
        available = [
            k for k in keys if k in sections
            and (sections[k]["items"] or sections[k]["has_more"])
        ]
        if available:
            chapters.append({
                "identity": key, "representation": title,
                "section_keys": available,
            })
            seen.update(available)

    remaining = [
        k for k, section in sections.items()
        if k not in seen and (section["items"] or section["has_more"])
    ]
    if remaining:
        chapters.append({
            "identity": "other", "representation": "Autres réalités",
            "section_keys": remaining,
        })

    operational_groups = (
        {"continuity"} if archetype in {
            SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY
        } else {"sessions", "registrations"} if archetype == SpaceArchetype.EDUCATION
        else {"requests", "cases", "occurrences"}
    )
    has_continuity = any(g["identity"] in operational_groups for g in chapters)
    has_portfolio = any(g["identity"] == "portfolio" for g in chapters)
    if (
        is_root and has_portfolio and not has_continuity
        and archetype != SpaceArchetype.EDUCATION
    ):
        chapters.sort(key=lambda g: 0 if g["identity"] == "portfolio" else 1)

    order = [k for g in chapters for k in g["section_keys"]]
    return {
        "preferred_language": label,
        "question": _QUESTIONS[archetype],
        "calm_message": (
            _CALM[archetype]
            if is_root and has_portfolio and not has_continuity else None
        ),
        "reading_groups": chapters,
        "perspectives": (
            [{
                "identity": "primary", "representation": label,
                # Optional owners are not yet all covered by this first group.
                "coverage_state": "partial",
                "sections": order,
                "creation_actions": [], "owner_handoffs": [],
            }] if order else []
        ),
        "selected_perspective": "primary" if order else None,
        "authority_scope": "activity_limited" if limited else "space",
    }
