"""C6 read models of real domain-owned external integrations.

These are deliberately NOT M7 ConnectionRefs, provider installations or Actions.
An integration is exposed only where its owning domain has real runtime facts;
mutation always returns to that domain's authenticated API/service.
"""
from django.conf import settings

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from notifications.models import PushEndpoint
from payments.integration_availability import payment_configuration_for
from payments.models import PaymentProvider


def _payment_capabilities(actor, *, allow_manual: bool) -> list[dict]:
    available = {
        row["value"] for row in payment_configuration_for(actor)["providers"]
    }
    rows = []
    if PaymentProvider.SANDBOX in available:
        rows.append({
            "code": "payments.sandbox",
            "owner": "payments",
            "kind": "processing_capability",
            "display_name": "Paiement de démonstration",
            "status": "sandbox_only",
            "available": True,
            "connected": False,
            "description": "Simulation Makolo uniquement. Aucun compte bancaire relié.",
            "links": {"configuration": "/api/v1/payments/configuration/"},
        })
    if allow_manual and PaymentProvider.MANUAL in available:
        rows.append({
            "code": "payments.manual",
            "owner": "payments",
            "kind": "processing_capability",
            "display_name": "Traitement manuel des paiements",
            "status": "manual_available",
            "available": True,
            "connected": False,
            "description": "Gestion manuelle selon l'autorité financière et les obligations réelles.",
            "links": {"configuration": "/api/v1/payments/configuration/"},
        })
    return rows


def profile_domain_integrations(actor) -> list[dict]:
    if not getattr(actor, "is_authenticated", False):
        return []
    rows = []
    count = PushEndpoint.objects.filter(user=actor, active=True).count()
    push_enabled = bool(getattr(settings, "MAKOLO_FIREBASE_PUSH_ENABLED", False))
    if count or push_enabled:
        rows.append({
            "code": "notifications.push",
            "owner": "notifications",
            "kind": "device_registration",
            "display_name": "Notifications sur mes appareils",
            "status": "registered" if count else "not_registered",
            "available": push_enabled,
            "connected": bool(count),
            "active_count": count,
            "description": "Appareils enregistrés pour les notifications Makolo.",
            "links": {"manage": "/api/v1/notifications/push/endpoints/"},
        })
    # Manual payment processing belongs to the *specific* Space/Activity or
    # Platform authority context, not to a global Profile. A person who has
    # finance.manage in one Space cannot act for every other Space from Moi.
    rows.extend(_payment_capabilities(actor, allow_manual=False))
    return rows


def space_domain_integrations(actor, space) -> list[dict]:
    if not getattr(actor, "is_authenticated", False):
        return []
    # Financial authority is separate from space.manage, membership, Platform.
    can_finance = has_direct_space_permission(
        actor, space, PermissionCode.FINANCE_MANAGE,
    )
    if not can_finance:
        return []
    return [
        row for row in _payment_capabilities(actor, allow_manual=True)
        if row["code"] == "payments.manual"
    ]


def platform_domain_integrations(actor) -> list[dict]:
    if not getattr(actor, "is_authenticated", False) or not can(
        actor, PermissionCode.PLATFORM_MANAGE
    ):
        return []
    return _payment_capabilities(actor, allow_manual=True)
