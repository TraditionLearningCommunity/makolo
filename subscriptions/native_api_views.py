"""Personal native subscription read/write façade, scoped to request.user."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing_models import PlanVersionBillingTerms, SubscriptionBillingObligation
from .contracts import AcquisitionMode, SubscriptionTransitionKind
from .models import PlanVersion
from .product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from .product_preview import build_subscription_change_preview
from .product_read import build_subscription_product_view
from .runtime_models import Subscription
from .security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)
from .transition_models import SubscriptionTransition, SubscriptionTransitionPaymentObligation


def _owned(request):
    return get_object_or_404(Subscription.objects.select_related("profile"), profile=request.user)


def _error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    raise exc


def _key(request):
    value = request.data.get("idempotency_key")
    if not isinstance(value, str) or not 8 <= len(value.strip()) <= 128:
        raise ValidationError({"idempotency_key": "Référence de confirmation requise."})
    return value.strip()


def _private(payload):
    response = Response(payload)
    response["Cache-Control"] = "private, no-store"
    return response


def _obligations(subscription, offset=0, limit=20):
    end = offset + limit + 1
    regular = (
        SubscriptionBillingObligation.objects.filter(subscription=subscription)
        .select_related("obligation").order_by("-created_at", "-id")[:end]
    )
    requirements = (
        SubscriptionTransitionPaymentObligation.objects.filter(transition__subscription=subscription)
        .select_related("obligation").order_by("-created_at", "-id")[:end]
    )
    by_id = {str(link.obligation_id): link.obligation for link in [*regular, *requirements]}
    ordered = sorted(by_id.values(), key=lambda o: (o.created_at, str(o.pk)), reverse=True)
    items = [
        {"id": str(o.pk), "label": o.label, "amount": str(o.amount),
         "currency": o.currency, "status": o.status, "due_at": o.due_at,
         "created_at": o.created_at}
        for o in ordered[offset:offset + limit]
    ]
    return {"items": items, "next_offset": offset + limit if len(ordered) > offset + limit else None}


def _snapshot(subscription):
    product = build_subscription_product_view(subscription, can_manage=True)
    entries = [product.current_base, *product.active_addons, *product.catalog]
    terms = {
        str(t.plan_version_id): {
            "amount": str(t.amount), "currency": t.currency,
            "period_unit": t.billing_period_unit, "period_count": t.billing_period_count,
        }
        for t in PlanVersionBillingTerms.objects.filter(
            plan_version_id__in=[row["plan_version_id"] for row in entries if row is not None]
        )
    }

    def decorate(row):
        return {**row, "billing_terms": terms.get(row["plan_version_id"])} if row is not None else None

    self_service = {
        str(pk) for pk in PlanVersion.objects.filter(
            pk__in=[r["plan_version_id"] for r in product.catalog],
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        ).values_list("pk", flat=True)
    }
    catalog = [decorate(row) for row in product.catalog]
    for row in catalog:
        row["can_request"] = bool(row["can_request"]) and row["plan_version_id"] in self_service
    return {
        "subscription": {
            "id": str(subscription.pk), "subject_label": product.subject_label,
            "status": product.status, "current_base": decorate(product.current_base),
            "active_addons": [decorate(row) for row in product.active_addons],
        },
        "capabilities": product.capabilities, "catalog": catalog,
        "transition": product.transition, "ongoing_conditions": product.ongoing_conditions,
        "billing": _obligations(subscription),
    }


class PersonalSubscriptionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subscription = Subscription.objects.filter(profile=request.user).first()
        return _private(_snapshot(subscription) if subscription else {"subscription": None})


class PersonalSubscriptionObligationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            offset = int(request.query_params.get("offset", "0"))
        except (ValueError, TypeError):
            raise ValidationError({"offset": "Pagination invalide."})
        if offset < 0 or offset > 500:
            raise ValidationError({"offset": "Pagination hors limites."})
        return _private(_obligations(_owned(request), offset=offset))


class PersonalSubscriptionPlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, plan_version_id):
        subscription = _owned(request)
        target = get_self_service_target(subscription, plan_version_id)
        try:
            preview = build_subscription_change_preview(
                subscription=subscription, kind=transition_kind_for_target(target),
                target_plan_version=target,
            )
        except DjangoValidationError as exc:
            _error(exc)
        terms = PlanVersionBillingTerms.objects.filter(plan_version=target).first()
        preview["billing_terms"] = (
            {"amount": str(terms.amount), "currency": terms.currency,
             "period_unit": terms.billing_period_unit, "period_count": terms.billing_period_count}
            if terms else None
        )
        return _private(preview)

    def post(self, request, plan_version_id):
        subscription = _owned(request)
        target = get_self_service_target(subscription, plan_version_id)
        key = _key(request)
        try:
            request_subscription_transition_for_actor(
                actor=request.user, subscription_id=subscription.pk,
                kind=transition_kind_for_target(target), target_plan_version_id=target.pk,
                request_origin="self_service", idempotency_key=key,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _private(_snapshot(subscription))


class PersonalSubscriptionAddonRemoveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, item_id):
        subscription = _owned(request)
        item = get_active_addon(subscription, item_id)
        try:
            preview = build_subscription_change_preview(
                subscription=subscription, kind=SubscriptionTransitionKind.ADDON_REMOVE,
                source_item=item,
            )
        except DjangoValidationError as exc:
            _error(exc)
        return _private(preview)

    def post(self, request, item_id):
        subscription = _owned(request)
        item = get_active_addon(subscription, item_id)
        key = _key(request)
        try:
            request_subscription_transition_for_actor(
                actor=request.user, subscription_id=subscription.pk,
                kind=SubscriptionTransitionKind.ADDON_REMOVE, source_item_id=item.pk,
                request_origin="self_service", idempotency_key=key,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _private(_snapshot(subscription))


class PersonalSubscriptionTransitionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transition_id, operation):
        subscription = _owned(request)
        transition = get_object_or_404(
            SubscriptionTransition, pk=transition_id, subscription=subscription
        )
        try:
            if operation == "cancel":
                cancel_subscription_transition_for_actor(
                    actor=request.user, transition_id=transition.pk,
                    reason="Annulée depuis l’application mobile.",
                )
            elif operation == "complete":
                complete_subscription_transition_for_actor(
                    actor=request.user, transition_id=transition.pk,
                )
            else:
                raise Http404
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _error(exc)
        return _private(_snapshot(subscription))
