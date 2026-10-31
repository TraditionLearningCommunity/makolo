"""Space Subscription native façade: the selected Space is the subscriber.

Reading and managing are independent Mandate permissions. The actor's
personal Subscription is never used to resolve Space entitlements.
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from .authorization import subscriptions_visible_to_actor
from .billing_models import PlanVersionBillingTerms
from .billing_presentation import subscription_billing_obligations, terms_as_dict
from .contracts import SubscriptionTransitionKind
from .native_api_views import _error, _key, _private, _replayed_intent, _snapshot
from .personal_history import subscription_transition_history
from .product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from .product_preview import build_subscription_change_preview
from .security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)
from .transition_models import SubscriptionTransition


def _space_subscription(actor, slug, *, manage=False):
    subscription = (
        subscriptions_visible_to_actor(actor, manage=manage)
        .filter(space__slug=slug)
        .select_related("space")
        .first()
    )
    if subscription is None:
        raise Http404
    return subscription


def _can_manage(actor, subscription):
    return subscriptions_visible_to_actor(actor, manage=True).filter(pk=subscription.pk).exists()


def _space_snapshot(actor, subscription):
    # Scope is recomputed for each response. A stale client-side Manage flag
    # never confers server authority.
    payload = _snapshot(subscription, can_manage=_can_manage(actor, subscription))
    # Payment details are a separate owner and may require FINANCE_VIEW.
    from payments.selectors import obligations_visible_to
    rows = payload["billing"]["items"]
    visible_ids = set(
        obligations_visible_to(actor).filter(pk__in=[row["id"] for row in rows])
        .values_list("pk", flat=True)
    )
    for row in rows:
        row["can_open_detail"] = any(str(pk) == row["id"] for pk in visible_ids)
    return _private(payload)


def _offset(request, maximum=100000):
    try:
        offset = int(request.query_params.get("offset", "0"))
    except (ValueError, TypeError) as exc:
        raise ValidationError({"offset": "Pagination invalide."}) from exc
    if not 0 <= offset <= maximum:
        raise ValidationError({"offset": "Pagination hors limites."})
    return offset


class SpaceSubscriptionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        subscription = _space_subscription(request.user, slug)
        return _space_snapshot(request.user, subscription)


class SpaceSubscriptionObligationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        subscription = _space_subscription(request.user, slug)
        payload = subscription_billing_obligations(subscription, offset=_offset(request))
        from payments.selectors import obligations_visible_to
        accessible = set(
            obligations_visible_to(request.user)
            .filter(pk__in=[row["id"] for row in payload["items"]])
            .values_list("pk", flat=True)
        )
        for row in payload["items"]:
            row["can_open_detail"] = any(str(pk) == row["id"] for pk in accessible)
        return _private(payload)


class SpaceSubscriptionHistoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        subscription = _space_subscription(request.user, slug)
        return _private(subscription_transition_history(subscription, offset=_offset(request)))


class SpaceSubscriptionPlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug, plan_version_id):
        subscription = _space_subscription(request.user, slug)
        target = get_self_service_target(subscription, plan_version_id)
        try:
            preview = build_subscription_change_preview(
                subscription=subscription, kind=transition_kind_for_target(target),
                target_plan_version=target,
            )
        except DjangoValidationError as exc:
            _error(exc)
        preview["billing_terms"] = terms_as_dict(
            PlanVersionBillingTerms.objects.filter(plan_version=target).first()
        )
        preview["can_confirm"] = _can_manage(request.user, subscription)
        return _private(preview)

    def post(self, request, slug, plan_version_id):
        subscription = _space_subscription(request.user, slug, manage=True)
        key = _key(request)
        if _replayed_intent(subscription, key=key, target_plan_version_id=plan_version_id):
            return _space_snapshot(request.user, subscription)
        target = get_self_service_target(subscription, plan_version_id)
        try:
            request_subscription_transition_for_actor(
                actor=request.user, subscription_id=subscription.pk,
                kind=transition_kind_for_target(target),
                target_plan_version_id=target.pk,
                request_origin="self_service", idempotency_key=key,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _space_snapshot(request.user, subscription)


class SpaceSubscriptionAddonRemoveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug, item_id):
        subscription = _space_subscription(request.user, slug)
        item = get_active_addon(subscription, item_id)
        try:
            preview = build_subscription_change_preview(
                subscription=subscription, kind=SubscriptionTransitionKind.ADDON_REMOVE,
                source_item=item,
            )
        except DjangoValidationError as exc:
            _error(exc)
        preview["can_confirm"] = _can_manage(request.user, subscription)
        return _private(preview)

    def post(self, request, slug, item_id):
        subscription = _space_subscription(request.user, slug, manage=True)
        key = _key(request)
        if _replayed_intent(subscription, key=key, source_item_id=item_id):
            return _space_snapshot(request.user, subscription)
        item = get_active_addon(subscription, item_id)
        try:
            request_subscription_transition_for_actor(
                actor=request.user, subscription_id=subscription.pk,
                kind=SubscriptionTransitionKind.ADDON_REMOVE,
                source_item_id=item.pk, request_origin="self_service",
                idempotency_key=key,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _space_snapshot(request.user, subscription)


class SpaceSubscriptionTransitionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug, transition_id, operation):
        subscription = _space_subscription(request.user, slug, manage=True)
        transition = get_object_or_404(
            SubscriptionTransition, pk=transition_id, subscription=subscription,
        )
        try:
            if operation == "cancel":
                cancel_subscription_transition_for_actor(
                    actor=request.user, transition_id=transition.pk,
                    reason="Annulée depuis l'application mobile de l'Espace.",
                )
            elif operation == "complete":
                complete_subscription_transition_for_actor(
                    actor=request.user, transition_id=transition.pk,
                )
            else:
                raise Http404
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _space_snapshot(request.user, subscription)
