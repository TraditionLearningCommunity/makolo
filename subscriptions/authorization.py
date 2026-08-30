from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import Http404

from authorization.constants import PermissionCode
from authorization.services import can, space_ids_with_permission

from .runtime_models import EntitlementGrant, Subscription
from .transition_models import SubscriptionRequirementAssessment, SubscriptionTransition


def _require_authenticated(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")


def _get_or_404(queryset, **lookup):
    try:
        return queryset.get(**lookup)
    except queryset.model.DoesNotExist as exc:
        raise Http404 from exc


def subscriptions_visible_to_actor(actor, *, manage=False):
    """Return only Subscriptions the actor is authorized to see or mutate.

    Profile self-authority is deliberately separate from Space Mandates. Platform
    authority is explicit and never inferred from Django ``is_staff``.
    """
    _require_authenticated(actor)
    platform_code = PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE if manage else PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW
    if can(actor, platform_code):
        return Subscription.objects.all()

    queryset = Subscription.objects.filter(profile=actor)
    space_code = PermissionCode.SPACE_SUBSCRIPTION_MANAGE if manage else PermissionCode.SPACE_SUBSCRIPTION_VIEW
    space_ids = space_ids_with_permission(actor, space_code)
    if space_ids is None:
        # Canonical authorization treats None as unbounded platform authority.
        return Subscription.objects.all()
    return queryset | Subscription.objects.filter(space_id__in=space_ids)


def get_subscription_for_actor(actor, subscription_id, *, manage=False):
    return _get_or_404(subscriptions_visible_to_actor(actor, manage=manage), pk=subscription_id)


def get_profile_subscription_for_actor(actor, subscription_id, *, manage=False):
    _require_authenticated(actor)
    platform_code = PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE if manage else PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW
    queryset = Subscription.objects.filter(profile=actor)
    if can(actor, platform_code):
        queryset = Subscription.objects.filter(profile__isnull=False)
    return _get_or_404(queryset, pk=subscription_id)


def get_space_subscription_for_actor(actor, subscription_id, *, manage=False):
    _require_authenticated(actor)
    platform_code = PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE if manage else PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW
    queryset = Subscription.objects.filter(space__isnull=False)
    if not can(actor, platform_code):
        space_code = PermissionCode.SPACE_SUBSCRIPTION_MANAGE if manage else PermissionCode.SPACE_SUBSCRIPTION_VIEW
        space_ids = space_ids_with_permission(actor, space_code)
        if space_ids is not None:
            queryset = queryset.filter(space_id__in=space_ids)
    return _get_or_404(queryset, pk=subscription_id)


def get_transition_for_actor(actor, transition_id, *, manage=False):
    subscription_ids = subscriptions_visible_to_actor(actor, manage=manage).values("pk")
    queryset = SubscriptionTransition.objects.filter(subscription_id__in=subscription_ids).select_related("subscription")
    return _get_or_404(queryset, pk=transition_id)


def get_subscription_assessment_for_actor(actor, assessment_id, *, manage=False):
    subscription_ids = subscriptions_visible_to_actor(actor, manage=manage).values("pk")
    queryset = SubscriptionRequirementAssessment.objects.filter(
        transition__subscription_id__in=subscription_ids
    ).select_related("transition", "transition__subscription", "plan_requirement")
    return _get_or_404(queryset, pk=assessment_id)


def get_entitlement_grant_for_actor(actor, grant_id):
    """Grant details are an internal platform concern, not self-service authority."""
    _require_authenticated(actor)
    if not can(actor, PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE):
        raise PermissionDenied("Permission Entitlement Grant requise.")
    return _get_or_404(EntitlementGrant.objects.select_related("feature", "profile", "space"), pk=grant_id)


def require_subscription_review_permission(actor):
    _require_authenticated(actor)
    if not can(actor, PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE):
        raise PermissionDenied("Permission de review Subscription requise.")
