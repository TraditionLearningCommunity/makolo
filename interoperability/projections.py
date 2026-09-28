from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .actions import ActionExecutionContext, ActionRegistry
from .extensions import ExtensionRegistry
from .registry import InteroperabilityRegistry
from .webhooks import WebhookSubscription


SCHEMA_VERSION = "z16.v1"


def project_providers(registry: InteroperabilityRegistry | None = None) -> list[dict[str, Any]]:
    if registry is None:
        return []
    return [
        {
            "code": provider.code,
            "available": True,
            "capabilities": sorted(provider.capabilities),
        }
        for provider in registry.providers()
    ]


def project_actions(
    registry: ActionRegistry | None = None,
    *,
    actor=None,
    authority_context=None,
    connection_available: bool = False,
) -> list[dict[str, Any]]:
    if registry is None:
        return []
    rows = []
    context = ActionExecutionContext(actor=actor, authority_context=authority_context)
    for action in registry.definitions():
        authorized = bool(action.authorize(context))
        available = not action.requires_connection or connection_available
        rows.append(
            {
                "code": action.code,
                "capability": action.capability,
                "owner": action.owner,
                "requires_connection": action.requires_connection,
                "available": available,
                "authorized": authorized,
                "idempotency_required": action.idempotent,
            }
        )
    return rows


def project_extensions(registry: ExtensionRegistry | None = None) -> list[dict[str, Any]]:
    if registry is None:
        return []
    return [
        {
            "code": extension.code,
            "actions": sorted(extension.actions),
            "read_projections": sorted(extension.read_projections),
            "ui_slots": sorted(extension.ui_slots),
            "available": True,
            "enabled": True,
        }
        for extension in registry.definitions()
    ]


def project_webhooks(
    subscriptions: Iterable[WebhookSubscription] = (),
    *,
    expose_event_families: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for subscription in sorted(subscriptions, key=lambda item: item.code):
        row: dict[str, Any] = {"code": subscription.code, "enabled": True}
        if expose_event_families:
            row["event_families"] = sorted(subscription.event_types)
        rows.append(row)
    return rows


def build_interoperability_payload(
    *,
    context: str,
    connections: list[dict[str, Any]],
    self_link: str,
    registry: InteroperabilityRegistry | None = None,
    action_registry: ActionRegistry | None = None,
    extension_registry: ExtensionRegistry | None = None,
    webhook_subscriptions: Iterable[WebhookSubscription] = (),
    actor=None,
    authority_context=None,
) -> dict[str, Any]:
    usable_connection = any(row.get("usable") for row in connections)
    return {
        "schema_version": SCHEMA_VERSION,
        "context": context,
        "providers": project_providers(registry),
        "connections": connections,
        "actions": project_actions(
            action_registry,
            actor=actor,
            authority_context=authority_context,
            connection_available=usable_connection,
        ),
        "extensions": project_extensions(extension_registry),
        "webhooks": project_webhooks(webhook_subscriptions),
        "links": {"self": self_link},
    }
