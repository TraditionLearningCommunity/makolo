"""User-invoked, owner-scoped clarification of a Discovery search.

No free-form chat, factual invention or new Action registry. The result only
contains bounded Discovery criteria; Discovery remains the search owner.
"""
from __future__ import annotations

from accounts.models import UserProfile
from intelligence.capabilities import IntelligenceCapability
from intelligence.gateway import IntelligenceGateway
from intelligence.runtime import build_runtime_registry

from .intent import resolve_discovery_intent
from .intelligence import interpret_with_intelligence


_ALLOWED_CRITERIA = frozenset({
    "q", "place", "when", "period", "vertical", "price",
    "date", "date_from", "date_to", "timezone",
})


def clarify_discovery_search(*, actor, criteria: dict) -> dict:
    """Explicit action, with no client-selected provider/owner or persistent effect."""
    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Authentification requise.")
    if not isinstance(criteria, dict) or set(criteria) - _ALLOWED_CRITERIA:
        raise ValueError("Critères non autorisés.")
    if not all(isinstance(value, str) for value in criteria.values()):
        raise ValueError("Critères invalides.")
    if any(len(value) > (120 if key == "q" else 160) for key, value in criteria.items()):
        raise ValueError("Critères trop longs.")
    params = {key: value.strip() for key, value in criteria.items()}
    intent = resolve_discovery_intent(params)
    status = "already_structured"
    if intent.raw_text and not intent.constraints:
        profile = UserProfile.objects.filter(user=actor).first()
        registry = build_runtime_registry(
            capability=IntelligenceCapability.STRUCTURED_GENERATE,
            profile=profile,
        )
        if not registry.providers_for(IntelligenceCapability.STRUCTURED_GENERATE):
            status = "unavailable"
        else:
            try:
                enriched = interpret_with_intelligence(
                    intent,
                    gateway=IntelligenceGateway(registry=registry),
                )
            except Exception:
                # No provider exception or credential details reach the client.
                enriched = intent
            status = "applied" if enriched != intent else "unchanged"
            intent = enriched
    elif not intent.raw_text:
        status = "empty"
    return {
        "status": status,
        "query": intent.to_search_params(),
        "constraints": [
            {
                "key": constraint.key,
                "value": constraint.value,
                "label": constraint.label,
                "source": constraint.source.value,
            }
            for constraint in intent.constraints
        ],
    }
