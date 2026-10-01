from __future__ import annotations

from dataclasses import dataclass

from .models import SpaceArchetype


@dataclass(frozen=True)
class SpaceOperatingPreset:
    """Presentation defaults derived from a Space archetype.

    This layer only influences product language, prioritization and suggested
    workflows. It never grants Permission, Mandate, Access or Entitlement, and
    it never forbids an Activity vertical.
    """

    label: str
    navigation_section_label: str
    activities_label: str
    featured_modules: tuple[str, ...]
    suggested_verticals: tuple[str, ...]


SPACE_OPERATING_PRESETS = {
    SpaceArchetype.GENERIC: SpaceOperatingPreset(
        label="Espace générique",
        navigation_section_label="Activité",
        activities_label="Activités",
        featured_modules=("activities", "requests", "groups", "crm", "analytics", "automation"),
        suggested_verticals=("event", "service", "obtention", "transport"),
    ),
    SpaceArchetype.CREATIVE: SpaceOperatingPreset(
        label="Artiste / création",
        navigation_section_label="Création",
        activities_label="Créations & activités",
        featured_modules=("activities", "crm", "audiences", "promotions", "growth", "partners", "analytics"),
        suggested_verticals=("event", "service", "obtention", "transport"),
    ),
    SpaceArchetype.MEDIA: SpaceOperatingPreset(
        label="Média / journalisme",
        navigation_section_label="Production",
        activities_label="Productions & activités",
        featured_modules=("activities", "crm", "audiences", "groups", "promotions", "growth", "partners", "trust", "analytics"),
        suggested_verticals=("event", "service", "obtention", "transport"),
    ),
    SpaceArchetype.EDUCATION: SpaceOperatingPreset(
        label="Enseignement / formation",
        navigation_section_label="Enseignement",
        activities_label="Programmes & activités",
        featured_modules=("activities", "requests", "groups", "access", "crm", "analytics", "automation"),
        suggested_verticals=("service", "event", "obtention", "transport"),
    ),
    SpaceArchetype.COMMERCE: SpaceOperatingPreset(
        label="Commerce / distribution",
        navigation_section_label="Offre",
        activities_label="Offres & activités",
        featured_modules=("activities", "offers", "orders", "payments", "crm", "promotions", "loyalty", "growth", "analytics"),
        suggested_verticals=("obtention", "service", "event", "transport"),
    ),
    SpaceArchetype.SERVICE_PROVIDER: SpaceOperatingPreset(
        label="Prestataire de services",
        navigation_section_label="Prestations",
        activities_label="Prestations & activités",
        featured_modules=("activities", "services", "requests", "crm", "offers", "orders", "payments", "analytics", "automation"),
        suggested_verticals=("service", "event", "obtention", "transport"),
    ),
    SpaceArchetype.TRANSPORT_OPERATOR: SpaceOperatingPreset(
        label="Opérateur de transport",
        navigation_section_label="Transport",
        activities_label="Services de transport & activités",
        featured_modules=("transport", "activities", "places", "access", "control", "orders", "payments", "operations", "crm", "analytics"),
        suggested_verticals=("transport", "service", "event", "obtention"),
    ),
    SpaceArchetype.COMMUNITY: SpaceOperatingPreset(
        label="Association / communauté",
        navigation_section_label="Vie collective",
        activities_label="Activités & initiatives",
        featured_modules=("activities", "groups", "crm", "funding", "partners", "recognition", "trust", "growth", "analytics", "automation"),
        suggested_verticals=("event", "service", "obtention", "transport"),
    ),
}


def operating_preset_for_space(space) -> SpaceOperatingPreset:
    try:
        archetype = SpaceArchetype(space.archetype)
    except (ValueError, AttributeError):
        archetype = SpaceArchetype.GENERIC
    return SPACE_OPERATING_PRESETS[archetype]



@dataclass(frozen=True)
class SpaceOperationalFootprint:
    """Derived use signals. This is a read model, never a source of truth."""

    signals: tuple[str, ...]


def operational_footprint_for_space(space) -> SpaceOperationalFootprint:
    signals = []
    activities = space.activities.all()
    if activities.exists():
        signals.append("activities")

    vertical_checks = (
        ("event", "event_vertical"),
        ("service", "service_details"),
        ("transport", "transport_service"),
        ("funding", "funding_details"),
        ("obtention", "obtention_details"),
    )
    for key, relation in vertical_checks:
        if activities.filter(**{f"{relation}__isnull": False}).exists():
            signals.append(key)

    if space.transport_routes.exists() or space.transport_vehicles.exists():
        signals.append("transport")
    if space.crm_contacts.exists():
        signals.append("crm")
    if space.collective_groups.exists():
        signals.append("groups")
    if space.partners.exists():
        signals.append("partners")
    if activities.filter(offers__isnull=False).exists() or space.commerce_orders.exists():
        signals.append("commerce")
    if space.payment_obligations.exists() or space.payer_payment_obligations.exists():
        signals.append("payments")
    if activities.filter(access_rights__isnull=False).exists():
        signals.append("access")
    if space.domain_automation_rules.exists() or space.crm_workflows.exists():
        signals.append("automation")
    if hasattr(space, "loyalty_program"):
        signals.append("loyalty")
    if space.trust_verification_claims.exists():
        signals.append("trust")

    return SpaceOperationalFootprint(signals=tuple(dict.fromkeys(signals)))
