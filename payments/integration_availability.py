"""Payment owner facts exposed to user journeys and Interoperability read models.

Payment providers do not represent user Connections. Only the sandbox and the
manual processing route exist in the current owner; never imply an external PSP.
"""
from django.conf import settings

from authorization.constants import PermissionCode
from authorization.services import (
    activity_ids_with_permission, has_platform_authority,
    space_ids_with_permission,
)
from payments.models import PaymentMethod, PaymentProvider


def can_manage_manual_payment(actor) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    return bool(
        has_platform_authority(actor)
        or space_ids_with_permission(actor, PermissionCode.FINANCE_MANAGE)
        or activity_ids_with_permission(actor, PermissionCode.ACTIVITY_FINANCE_MANAGE)
    )


def payment_configuration_for(actor) -> dict:
    providers = []
    sandbox = bool(getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False))
    if sandbox:
        providers.append(PaymentProvider.SANDBOX)
    if can_manage_manual_payment(actor):
        providers.append(PaymentProvider.MANUAL)
    return {
        "providers": [
            {"value": value, "label": label}
            for value, label in PaymentProvider.choices if value in providers
        ],
        "methods": [
            {"value": value, "label": label}
            for value, label in PaymentMethod.choices
        ],
        "sandbox_enabled": sandbox,
    }
