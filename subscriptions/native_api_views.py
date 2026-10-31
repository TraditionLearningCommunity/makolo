"""Personal native subscription read/write façade, scoped to request.user."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing_models import PlanVersionBillingTerms
from .billing_presentation import (
    personal_billing_obligations,
    terms_as_dict,
    with_billing_terms,
)
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
from .transition_models import SubscriptionTransition


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


def _replayed_intent(subscription, *, key, target_plan_version_id=None, source_item_id=None):
    """Return an already authorized self-service intent without re-acquiring its target.

    A completed add-on is no longer active, and a completed BASE may become
    current. In both cases the original idempotency key must still replay.
    """
    transition = SubscriptionTransition.objects.filter(
        subscription=subscription, idempotency_key=key
    ).first()
    if transition is None:
        return False
    matching = (
        transition.request_origin == "self_service"
        and (
            target_plan_version_id is not None
            and transition.kind in {"base_switch", "addon_add"}
            and transition.source_item_id is None
            and str(transition.target_plan_version_id) == str(target_plan_version_id)
            or source_item_id is not None
            and transition.kind == "addon_remove"
            and str(transition.source_item_id) == str(source_item_id)
        )
    )
    if not matching:
        raise ValidationError({"idempotency_key": "Cette référence appartient à une autre demande."})
    return True


def _snapshot(subscription):
    product = with_billing_terms(build_subscription_product_view(subscription, can_manage=True))
    self_service = {
        str(pk) for pk in PlanVersion.objects.filter(
            pk__in=[row["plan_version_id"] for row in product.catalog],
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        ).values_list("pk", flat=True)
    }
    catalog = [dict(row) for row in product.catalog]
    for row in catalog:
        row["can_request"] = bool(row["can_request"]) and row["plan_version_id"] in self_service
    return {
        "subscription": {
            "id": str(subscription.pk),
            "subject_label": product.subject_label,
            "status": product.status,
            "current_base": product.current_base,
            "active_addons": product.active_addons,
        },
        "capabilities": product.capabilities,
        "catalog": catalog,
        "transition": product.transition,
        "ongoing_conditions": product.ongoing_conditions,
        "billing": personal_billing_obligations(subscription),
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
        return _private(personal_billing_obligations(_owned(request), offset=offset))


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
        preview["billing_terms"] = terms_as_dict(terms)
        return _private(preview)

    def post(self, request, plan_version_id):
        subscription = _owned(request)
        key = _key(request)
        if _replayed_intent(subscription, key=key, target_plan_version_id=plan_version_id):
            return _private(_snapshot(subscription))
        target = get_self_service_target(subscription, plan_version_id)
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
        key = _key(request)
        if _replayed_intent(subscription, key=key, source_item_id=item_id):
            return _private(_snapshot(subscription))
        item = get_active_addon(subscription, item_id)
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
