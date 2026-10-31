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
    # Orders are not payments or proof of fulfilment; offers are durable
    # availability, even when there are no current orders.
    SpaceArchetype.COMMERCE: (
        ("orders", "Commandes et traitement",
         ("preparation", "active", "blocked")),
        ("availability", "Ce que nous rendons disponible",
         ("offers", "activities")),
        ("realizations", "Réalisations à venir", ("upcoming",)),
        ("specialized", "Autres réalités opérées",
         ("requests", "routes", "vehicles")),
        ("history", "Historique commercial", ("completed",)),
    ),
    # Departure = Occurrence + TransportDeparture. Routes and vehicles remain
    # structural owners regardless of their active flag.
    SpaceArchetype.TRANSPORT_OPERATOR: (
        ("departures", "Départs et exploitation",
         ("active", "upcoming", "preparation", "blocked")),
        ("structure", "Routes et véhicules", ("routes", "vehicles")),
        ("services", "Services de transport", ("activities",)),
        ("specialized", "Autres réalités opérées",
         ("offers", "requests")),
        ("history", "Départs et activités passés", ("completed",)),
    ),
    # Creation is a contextual Activity identity, not another stored model.
    # Never make a commerce Offer the leading artistic identity.
    SpaceArchetype.CREATIVE: (
        ("creation_work", "Créations à faire avancer",
         ("active", "preparation", "blocked")),
        ("presentations", "Présentations et dates",
         ("upcoming",)),
        ("creations", "Créations durables", ("activities",)),
        ("related", "Autres réalités opérées",
         ("requests", "offers", "routes", "vehicles")),
        ("history", "Créations et réalisations passées", ("completed",)),
    ),
    # An editorial Production is durable. An edition or recording is an
    # Occurrence; a file or media use alone is never promoted to a Production.
    SpaceArchetype.MEDIA: (
        ("production_work", "Productions à faire avancer",
         ("active", "preparation", "blocked")),
        ("realizations", "Éditions et réalisations à venir",
         ("upcoming",)),
        ("productions", "Productions durables", ("activities",)),
        ("related", "Autres réalités opérées",
         ("requests", "offers", "routes", "vehicles")),
        ("history", "Productions et réalisations passées", ("completed",)),
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
    SpaceArchetype.COMMERCE: (
        "Que rendons-nous disponible, quelles commandes traiter et "
        "quelles réalisations devons-nous réellement accomplir ?"
    ),
    SpaceArchetype.TRANSPORT_OPERATOR: (
        "Quels départs préparons-nous et opérons-nous, sur quelles routes "
        "et avec quels véhicules réellement affectés ?"
    ),
    SpaceArchetype.CREATIVE: (
        "Quelles œuvres créons-nous, que faut-il préparer et "
        "quelles présentations réelles arrivent ?"
    ),
    SpaceArchetype.MEDIA: (
        "Quelles productions réalisons-nous, quelles éditions préparons-nous "
        "et qu’est-ce qui doit être diffusé ou présenté ?"
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
    SpaceArchetype.COMMERCE: (
        "Aucune commande ne demande d’intervention dans cette vue. "
        "L’offre disponible reste accessible."
    ),
    SpaceArchetype.TRANSPORT_OPERATOR: (
        "Aucun départ ne demande d’intervention dans cette vue. "
        "Les routes et véhicules restent accessibles."
    ),
    SpaceArchetype.CREATIVE: (
        "Aucune préparation ou présentation n’appelle d’intervention dans cette "
        "vue. Les créations durables restent accessibles."
    ),
    SpaceArchetype.MEDIA: (
        "Aucune édition ni réalisation n’appelle d’intervention dans cette "
        "vue. Les productions durables restent accessibles."
    ),
}


def compose_space_work_business_world(*, archetype, label, sections, limited, is_root=True, today=None):
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
        if archetype == SpaceArchetype.SERVICE_PROVIDER
        else {"orders", "realizations"} if archetype == SpaceArchetype.COMMERCE
        else {"departures"} if archetype == SpaceArchetype.TRANSPORT_OPERATOR
        else {"creation_work", "presentations"}
        if archetype == SpaceArchetype.CREATIVE
        else {"production_work", "realizations"}
    )
    has_continuity = any(g["identity"] in operational_groups for g in chapters)
    has_portfolio = any(
        g["identity"] in {
            "portfolio", "availability", "structure", "services",
            "creations", "productions",
        }
        for g in chapters
    )
    if (
        is_root and has_portfolio and not has_continuity
        and archetype != SpaceArchetype.EDUCATION
    ):
        chapters.sort(key=lambda g: (
            0 if g["identity"] in {
                "portfolio", "availability", "structure", "creations", "productions",
            } else 1
        ))

    order = [k for g in chapters for k in g["section_keys"]]
    # The contextual Today lens is a reference to visible real departures,
    # never a duplicate entry, an urgency score or a newly stored lifecycle.
    today_departures = []
    if archetype == SpaceArchetype.TRANSPORT_OPERATOR and is_root and today:
        for section_key in ("active", "upcoming"):
            for item in sections.get(section_key, {}).get("items", ()):
                if (
                    item.get("kind") == "departure"
                    and item.get("timing", {}).get("start_date") == today
                ):
                    today_departures.append({
                        "source": item["source"],
                        "title": item["title"],
                        "section": section_key,
                        "start_time": item["timing"].get("start_time"),
                    })
        today_departures = today_departures[:5]
    return {
        "preferred_language": label,
        "question": _QUESTIONS[archetype],
        **({"today_departures": today_departures}
           if archetype == SpaceArchetype.TRANSPORT_OPERATOR else {}),
        "calm_message": (
            _CALM[archetype]
            if is_root and has_portfolio and not has_continuity else None
        ),
        "reading_groups": chapters,
        "perspectives": (
            [{
                "identity": "primary", "representation": label,
                # Coverage is scoped to sources known in this perspective;
                # limited authority cannot prove the whole Space is empty.
                "coverage_state": (
                    "partial" if limited or any(
                        sections[k]["coverage_state"] != "established"
                        for k in order
                    ) else "established"
                ),
                "sections": order,
                "creation_actions": [], "owner_handoffs": [],
            }] if order else []
        ),
        "selected_perspective": "primary" if order else None,
        "authority_scope": "activity_limited" if limited else "space",
    }
