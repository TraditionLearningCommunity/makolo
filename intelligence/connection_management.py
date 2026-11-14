"""Owner-controlled, provider-specific self-service Intelligence connections.

This does not implement generic M7 OAuth or mutate any ConnectionRef.
User-supplied keys are stored exclusively by Intelligence's encrypted credential owner.
"""
from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import connection as db_connection, transaction

from accounts.models import UserProfile
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
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


def _assert_management(*, actor, scope, profile=None, space=None):
    if scope == ProviderScope.PROFILE:
        if profile is None or profile.user_id != actor.pk:
            raise PermissionDenied("Profil non autorisé.")
        return
    if scope == ProviderScope.SPACE:
        if space is None or not has_direct_space_permission(
            actor, space, PermissionCode.SPACE_MANAGE,
        ):
            raise PermissionDenied("Autorité Space requise.")
        return
    if scope == ProviderScope.PLATFORM and can(actor, PermissionCode.PLATFORM_MANAGE):
        return
    raise PermissionDenied("Autorité insuffisante.")


def _serialize_platform_creates() -> None:
    """Transaction-scoped Postgres mutex shared by *all* Platform operators.

    Locking each operator independently cannot prevent two actors creating
    the same logical provider connection concurrently. No database state is
    introduced; non-Postgres development DBs remain best-effort.
    """
    if db_connection.vendor != "postgresql":
        return
    lock_key = int.from_bytes(
        hashlib.sha256(
            b"makolo:intelligence:platform-provider-create:v1"
        ).digest()[:8],
        byteorder="big",
        signed=True,
    )
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])


@transaction.atomic
def create_connection(*, actor, scope, payload, space=None):
    """Create one concrete provider connection, routes and encrypted credential atomically."""
    if not isinstance(payload, dict):
        raise ValidationError("Données invalides.")
    if set(payload) - {"provider", "name", "api_key", "model", "consent"}:
        raise ValidationError("Champs non autorisés.")
    if payload.get("consent") is not True:
        raise ValidationError({"consent": "Confirmez l'usage de votre clé pour ce fournisseur."})
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
        profile, _ = UserProfile.objects.get_or_create(user=actor)
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        _assert_management(actor=actor, scope=scope, profile=profile)
        owner = _owner_filter(scope=scope, profile=profile)
    elif scope == ProviderScope.SPACE:
        # The authorization gate belongs to the caller and is rechecked at API entry.
        from organizations.models import Organization
        if space is None:
            raise PermissionDenied("Espace requis.")
        locked_space = Organization.objects.select_for_update().get(pk=space.pk)
        _assert_management(actor=actor, scope=scope, space=locked_space)
        owner = _owner_filter(scope=scope, space=locked_space)
    else:
        # Platform operators share one logical owner. Serialize the existence
        # check across operators on PostgreSQL before checking duplicates.
        _serialize_platform_creates()
        type(actor).objects.select_for_update().get(pk=actor.pk)
        _assert_management(actor=actor, scope=scope)
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
    from operations.services import audit_action
    audit_action(
        actor=actor, action="intelligence.connection_created",
        target_type="provider_connection", target_id=connection.pk,
        summary="Connexion Intelligence personnelle ou collective établie",
        after={"scope":scope, "protocol":offer.protocol},
        metadata={"credential_consent": True},
    )
    return connection


@transaction.atomic
def update_connection(*, actor, connection, payload):
    if not isinstance(payload, dict) or not payload or set(payload) - {"enabled", "api_key"}:
        raise ValidationError("Champs non autorisés.")
    enabled = payload.get("enabled")
    if "enabled" in payload and not isinstance(enabled, bool):
        raise ValidationError({"enabled": "Valeur booléenne requise."})
    secret = None
    if "api_key" in payload:
        secret = _validate_string(payload["api_key"], field="api_key", max_length=4096, required=True)
    connection = ProviderConnection.objects.select_related("profile", "space").select_for_update().get(pk=connection.pk)
    _assert_management(
        actor=actor, scope=connection.scope,
        profile=connection.profile, space=connection.space,
    )
    if (connection.default_model == "demo-disabled" or connection.name.startswith("[DEMO Connexion] ")) and (enabled is True or secret is not None):
        raise ValidationError("Cette simulation ne peut pas être activée ni recevoir de clé externe.")
    previous_enabled = connection.enabled
    if enabled is True and not hasattr(connection, "credential") and secret is None:
        raise ValidationError({"enabled": "Une clé est nécessaire pour activer cette connexion."})
    if secret is not None:
        set_provider_secret(connection=connection, secret=secret)
    if secret is not None or (enabled is True and not previous_enabled):
        # A rotated credential or restored channel has no verified health yet.
        connection.health_status = ProviderHealth.UNKNOWN
        connection.last_checked_at = None
        connection.last_latency_ms = None
    if enabled is not None:
        connection.enabled = enabled
    connection.save(update_fields=[
        "enabled", "health_status", "last_checked_at",
        "last_latency_ms", "updated_at",
    ])
    from operations.services import audit_action
    audit_action(
        actor=actor, action="intelligence.connection_updated",
        target_type="provider_connection", target_id=connection.pk,
        summary="Paramètres d'activation ou clé Intelligence modifiés",
        before={"enabled": previous_enabled},
        after={"enabled": connection.enabled},
        metadata={"scope": connection.scope, "credential_rotated": secret is not None},
    )
    return connection


@transaction.atomic
def disconnect_connection(*, actor, connection):
    """Remove the local channel AND encrypted credential; external key remains provider-owned."""
    connection = ProviderConnection.objects.select_related("profile", "space").select_for_update().get(pk=connection.pk)
    _assert_management(
        actor=actor, scope=connection.scope,
        profile=connection.profile, space=connection.space,
    )
    previous_enabled = connection.enabled
    connection.enabled = False
    connection.save(update_fields=["enabled", "updated_at"])
    from operations.services import audit_action
    audit_action(
        actor=actor, action="intelligence.connection_removed",
        target_type="provider_connection", target_id=connection.pk,
        summary="Connexion Intelligence retirée et credential local supprimé",
        before={"scope": connection.scope, "enabled": previous_enabled},
        after={"removed": True},
    )
    connection.delete()
