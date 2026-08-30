from __future__ import annotations

from django.core.exceptions import PermissionDenied

from authorization.constants import PermissionCode
from authorization.services import can

from .authorization import get_subscription_for_actor, get_transition_for_actor
from .models import PlanVersion
from .runtime_models import EntitlementGrant
from .runtime_services import create_entitlement_grant, revoke_entitlement_grant
from .transition_services import (
    cancel_subscription_transition,
    complete_subscription_transition,
    request_subscription_transition,
)


def _require_grant_authority(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if not can(actor, PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE):
        raise PermissionDenied("Permission Entitlement Grant requise.")


def request_subscription_transition_for_actor(
    *,
    actor,
    subscription_id,
    kind,
    target_plan_version_id=None,
    source_item=None,
    request_origin="self_service",
    idempotency_key,
    expires_at=None,
    reason="",
):
    """Authorization-aware application entry point for S4 transition requests."""
    subscription = get_subscription_for_actor(actor, subscription_id, manage=True)
    target = None
    if target_plan_version_id is not None:
        target = PlanVersion.objects.select_related("plan").get(pk=target_plan_version_id)
    return request_subscription_transition(
        subscription=subscription,
        kind=kind,
        target_plan_version=target,
        source_item=source_item,
        requested_by=actor,
        request_origin=request_origin,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
        reason=reason,
    )


def cancel_subscription_transition_for_actor(*, actor, transition_id, reason=""):
    transition = get_transition_for_actor(actor, transition_id, manage=True)
    return cancel_subscription_transition(transition=transition, actor=actor, reason=reason)


def complete_subscription_transition_for_actor(*, actor, transition_id):
    transition = get_transition_for_actor(actor, transition_id, manage=True)
    return complete_subscription_transition(transition=transition)


def create_entitlement_grant_for_actor(
    *, actor, feature, value, reason, profile=None, space=None, valid_from=None, valid_until=None
):
    """Create a controlled exception; subject self-authority never grants this permission."""
    _require_grant_authority(actor)
    return create_entitlement_grant(
        feature=feature,
        value=value,
        reason=reason,
        profile=profile,
        space=space,
        granted_by=actor,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def revoke_entitlement_grant_for_actor(*, actor, grant_id, reason):
    _require_grant_authority(actor)
    grant = EntitlementGrant.objects.get(pk=grant_id)
    return revoke_entitlement_grant(grant=grant, actor=actor, reason=reason)
