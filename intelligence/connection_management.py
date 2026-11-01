"""Owner-controlled, provider-specific self-service Intelligence connections.

This does not implement generic M7 OAuth or mutate any ConnectionRef.
User-supplied keys are stored exclusively by Intelligence's encrypted credential owner.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction

from accounts.models import UserProfile
from intelligence.capabilities import IntelligenceCapability
from intelligence.credentials import set_provider_secret
from intelligence.models import (
    IntelligenceRoute, ProviderConnection, ProviderHealth,
    ProviderProtocol, ProviderScope,
)


@dataclass(frozen=True)
class ConnectionOffer:
    code: str
    label: str
    description: str
    protocol: str
    base_url: str
    capabilities: tuple[str, ...]
    requires_model: bool = False


# Fixed public HTTPS endpoints avoid accepting user-provided network destinations.
# These are NOT OAuth grants; the user must supply their own provider-issued key.
OFFERS = {
    "tavily": ConnectionOffer(
        "tavily", "Tavily", "Recherche Web avec votre propre clé Tavily.",
        ProviderProtocol.TAVILY_SEARCH, "https://api.tavily.com",
        (IntelligenceCapability.WEB_RESEARCH.value,),
    ),
    "exa": ConnectionOffer(
        "exa", "Exa", "Recherche Web avec votre propre clé Exa.",
        ProviderProtocol.EXA_SEARCH, "https://api.exa.ai",
        (IntelligenceCapability.WEB_RESEARCH.value,),
    ),
    "openai": ConnectionOffer(
        "openai", "OpenAI API", "Génération et représentation sémantique avec votre clé API.",
        ProviderProtocol.OPENAI_COMPATIBLE, "https://api.openai.com/v1",
        (
            IntelligenceCapability.TEXT_GENERATE.value,
            IntelligenceCapability.STRUCTURED_GENERATE.value,
            IntelligenceCapability.EMBED.value,
        ),
        True,
    ),
    "openai_web": ConnectionOffer(
        "openai_web", "OpenAI Web Research", "Recherche Web via Responses avec votre clé API.",
        ProviderProtocol.OPENAI_RESPONSES_WEB, "https://api.openai.com/v1",
        (IntelligenceCapability.WEB_RESEARCH.value,),
        True,
    ),
}


def catalog() -> list[dict]:
    configured = bool(os.environ.get("INTELLIGENCE_CREDENTIAL_MASTER_KEY", "").strip())
    return [
        {
            "code": offer.code,
            "label": offer.label,
            "description": offer.description,
            "capabilities": list(offer.capabilities),
            "requires_model": offer.requires_model,
            "can_connect": configured,
        }
        for offer in OFFERS.values()
    ]


def _validate_string(value, *, field, max_length, required=False) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise ValidationError({field: "Valeur invalide."})
    value = value.strip()
    if required and not value:
        raise ValidationError({field: "Ce champ est obligatoire."})
    return value


def _owner_filter(*, scope, profile=None, space=None):
    if scope == ProviderScope.PROFILE and profile is not None:
        return {"scope": scope, "profile": profile}
    if scope == ProviderScope.SPACE and space is not None:
        return {"scope": scope, "space": space}
    if scope == ProviderScope.PLATFORM and profile is None and space is None:
        return {"scope": scope}
    raise ValidationError("Portée de connexion invalide.")


@transaction.atomic
def create_connection(*, actor, scope, payload, space=None):
    """Create one concrete provider connection, routes and encrypted credential atomically."""
    if not isinstance(payload, dict):
        raise ValidationError("Données invalides.")
    if set(payload) - {"provider", "name", "api_key", "model"}:
        raise ValidationError("Champs non autorisés.")
    provider = _validate_string(payload.get("provider"), field="provider", max_length=30, required=True)
    offer = OFFERS.get(provider)
    if offer is None:
        raise ValidationError({"provider": "Fournisseur non pris en charge."})
    name = _validate_string(payload.get("name", offer.label), field="name", max_length=120, required=True)
    key = _validate_string(payload.get("api_key"), field="api_key", max_length=4096, required=True)
    model = _validate_string(payload.get("model", ""), field="model", max_length=160)
    if offer.requires_model and not model:
        raise ValidationError({"model": "Le modèle est obligatoire."})
    if not offer.requires_model and model:
        raise ValidationError({"model": "Ce fournisseur n'utilise pas de modèle."})
    if not os.environ.get("INTELLIGENCE_CREDENTIAL_MASTER_KEY", "").strip():
        raise ImproperlyConfigured("Intelligence credentials are not configured.")

    if scope == ProviderScope.PROFILE:
        # Lock the existing canonical Profile row to prevent duplicate concurrent submissions.
        profile = UserProfile.objects.select_for_update().get(user=actor)
        owner = _owner_filter(scope=scope, profile=profile)
    elif scope == ProviderScope.SPACE:
        # The authorization gate belongs to the caller and is rechecked at API entry.
        from organizations.models import Organization
        locked_space = Organization.objects.select_for_update().get(pk=space.pk)
        owner = _owner_filter(scope=scope, space=locked_space)
    else:
        # Platform lifecycle is technical; serialize changes on the current operator.
        type(actor).objects.select_for_update().get(pk=actor.pk)
        owner = _owner_filter(scope=scope)

    if ProviderConnection.objects.filter(**owner, protocol=offer.protocol, base_url=offer.base_url, name=name).exists():
        raise ValidationError({"name": "Une connexion portant ce nom existe déjà."})

    connection = ProviderConnection(
        **owner, name=name, protocol=offer.protocol, base_url=offer.base_url,
        default_model=model, enabled=True, health_status=ProviderHealth.UNKNOWN,
    )
    connection.full_clean()
    connection.save()
    set_provider_secret(connection=connection, secret=key)
    for capability in offer.capabilities:
        IntelligenceRoute.objects.create(connection=connection, capability=capability)
    return connection


@transaction.atomic
def update_connection(*, connection, payload):
    if not isinstance(payload, dict) or not payload or set(payload) - {"enabled", "api_key"}:
        raise ValidationError("Champs non autorisés.")
    enabled = payload.get("enabled")
    if "enabled" in payload and not isinstance(enabled, bool):
        raise ValidationError({"enabled": "Valeur booléenne requise."})
    secret = None
    if "api_key" in payload:
        secret = _validate_string(payload["api_key"], field="api_key", max_length=4096, required=True)
    connection = ProviderConnection.objects.select_for_update().get(pk=connection.pk)
    if secret is not None:
        set_provider_secret(connection=connection, secret=secret)
        connection.health_status = ProviderHealth.UNKNOWN
    if enabled is True and not hasattr(connection, "credential") and secret is None:
        raise ValidationError({"enabled": "Une clé est nécessaire pour activer cette connexion."})
    if enabled is not None:
        connection.enabled = enabled
    connection.save(update_fields=["enabled", "health_status", "updated_at"])
    return connection


@transaction.atomic
def disconnect_connection(*, connection):
    """Remove the local channel AND encrypted credential; external key remains provider-owned."""
    connection = ProviderConnection.objects.select_for_update().get(pk=connection.pk)
    connection.enabled = False
    connection.save(update_fields=["enabled", "updated_at"])
    connection.delete()
