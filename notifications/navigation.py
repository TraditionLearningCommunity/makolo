from __future__ import annotations

from django.urls import reverse


NOTIFICATION_NAVIGATION_SCHEMA_VERSION = 1

_METADATA_IDENTIFIER_KEYS = (
    "event_id",
    "order_id",
    "payment_id",
    "ticket_id",
    "activity_id",
    "journey_id",
    "access_id",
    "occurrence_id",
    "conversation_id",
    "group_id",
    "partner_id",
    "dossier_id",
    "project_id",
    "personal_asset_id",
)

# Keep the historical Event/Ticket/Payment precedence stable, then prefer the
# most specific Mature owner surface before falling back to Activity.
_TARGET_PRIORITY = (
    ("ticket", "ticket_id", "ticket"),
    ("payment", "payment_id", "payment"),
    ("order", "order_id", "ticket_order"),
    ("event", "event_id", "event"),
    ("access", "access_id", "access"),
    ("journey", "journey_id", "journey"),
    ("occurrence", "occurrence_id", "occurrence"),
    ("conversation", "conversation_id", "conversation"),
    ("group", "group_id", "group"),
    ("partner", "partner_id", "partner_relationship"),
    ("dossier", "dossier_id", "dossier"),
    ("project", "project_id", "project"),
    ("resource", "personal_asset_id", "personal_asset"),
    ("activity", "activity_id", "activity"),
)


def _identifier(value):
    if value in (None, ""):
        return None
    return str(value)


def notification_identifiers(notification) -> dict[str, str]:
    """Return only explicit structured identifiers already attached to the notification."""
    metadata = notification.metadata if isinstance(notification.metadata, dict) else {}
    identifiers = {}
    for key in _METADATA_IDENTIFIER_KEYS:
        value = _identifier(metadata.get(key))
        if value is not None:
            identifiers[key] = value

    # Canonical direct FKs are stronger than a duplicated metadata value.
    for attribute, key in (
        ("activity_id", "activity_id"),
        ("journey_id", "journey_id"),
        ("access_id", "access_id"),
    ):
        value = _identifier(getattr(notification, attribute, None))
        if value is not None:
            identifiers[key] = value
    return identifiers


def _api_link(target: str, resource_id: str) -> str | None:
    if target == "ticket":
        return f"/api/v1/tickets/tickets/{resource_id}/"
    if target == "payment":
        return f"/api/v1/payments/payments/{resource_id}/"
    if target == "order":
        return f"/api/v1/tickets/orders/{resource_id}/"
    if target == "access":
        return reverse("personal-detail-projections:access-detail", kwargs={"pk": resource_id})
    if target == "journey":
        return reverse("personal-detail-projections:journey-detail", kwargs={"pk": resource_id})
    if target == "occurrence":
        return reverse("occurrences_api:detail", kwargs={"pk": resource_id})
    if target == "conversation":
        return reverse("conversations-api:detail", kwargs={"pk": resource_id})
    if target == "group":
        return reverse("personal-projections:group-detail", kwargs={"pk": resource_id})
    if target == "partner":
        return reverse("personal-projections:partner-detail", kwargs={"pk": resource_id})
    if target == "dossier":
        return reverse("objectives_api:dossier-detail", kwargs={"pk": resource_id})
    if target == "project":
        return reverse("objectives_api:project-detail", kwargs={"pk": resource_id})
    if target == "resource":
        return reverse("personal-projections:resource-detail", kwargs={"pk": resource_id})
    if target == "activity":
        return reverse("activities_api:detail", kwargs={"pk": resource_id})
    # Event compatibility requires a slug for the participant detail, so an
    # event UUID alone deliberately carries no invented API link.
    return None


def build_notification_navigation(notification) -> dict | None:
    """Build an additive, owner-directed navigation hint without inferring authority.

    The notification only identifies a destination. The destination endpoint is
    still responsible for visibility, authority and current-state validation and
    may legitimately answer 404/403.
    """
    identifiers = notification_identifiers(notification)
    target = resource_kind = resource_id = None
    for candidate, key, candidate_kind in _TARGET_PRIORITY:
        if identifiers.get(key):
            target = candidate
            resource_kind = candidate_kind
            resource_id = identifiers[key]
            break

    if target is None:
        return None

    payload = {
        "schema_version": NOTIFICATION_NAVIGATION_SCHEMA_VERSION,
        "target": target,
        **identifiers,
        "resource": {
            "kind": resource_kind,
            "id": resource_id,
        },
    }
    api_link = _api_link(target, resource_id)
    if api_link:
        payload["links"] = {"api": api_link}
    return payload
