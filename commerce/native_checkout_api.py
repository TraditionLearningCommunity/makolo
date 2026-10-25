"""Commerce-owned checkout for an *existing* personal Journey.

No client-created Journey, price, payment, access or capacity truth.
"""
from django.core.exceptions import ValidationError as DomainValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import ActivityStatus, ActivityVisibility
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer, PaymentMode
from commerce.selectors import currently_available_offers
from commerce.services import create_order
from groups.community_services import profile_is_eligible_for_activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from payments.models import PaymentObligation
from payments.obligation_services import create_commerce_payment_obligation


ALLOWED_WORKFLOWS = {
    WorkflowKind.PURCHASE, WorkflowKind.ORDER_APPROVAL, WorkflowKind.RESERVATION,
}
ACTIVE_ORDER_STATUSES = {
    CommerceOrderStatus.PENDING, CommerceOrderStatus.CONFIRMED,
}


class CommerceCheckoutInput(serializers.Serializer):
    offer_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=10000)
    payment_mode = serializers.ChoiceField(choices=PaymentMode.choices)
    idempotency_key = serializers.CharField(max_length=128, allow_blank=False)


def _journey_for_actor(actor, journey_id, *, lock=False):
    qs = Journey.objects.filter(beneficiary=actor).select_related("activity", "occurrence")
    if lock:
        qs = qs.select_for_update()
    return get_object_or_404(qs, pk=journey_id)


def _active_order(journey):
    return (
        CommerceOrder.objects.filter(journey=journey, status__in=ACTIVE_ORDER_STATUSES)
        .order_by("-created_at", "-pk").first()
    )


def _order_payload(order):
    obligation = PaymentObligation.objects.filter(commerce_order=order).order_by("-created_at").first()
    return {
        "kind": "commerce_order",
        "id": str(order.pk),
        "journey_id": str(order.journey_id),
        "reference": order.reference,
        "status": order.status,
        "total": str(order.total),
        "currency": order.currency,
        "payment_mode": order.payment_mode,
        "payment_obligation_id": str(obligation.pk) if obligation else None,
        "payment_obligation_status": obligation.status if obligation else None,
    }


def _checkout_offers(journey):
    return currently_available_offers(
        activity=journey.activity,
        occurrence=journey.occurrence,
    ).prefetch_related("payment_options")


def _allowed_to_checkout(actor, journey):
    if (
        journey.workflow not in ALLOWED_WORKFLOWS
        or journey.status in {
            JourneyStatus.FULFILLED, JourneyStatus.REJECTED,
            JourneyStatus.CANCELLED, JourneyStatus.EXPIRED,
        }
        or journey.activity.status != ActivityStatus.PUBLISHED
        or journey.activity.visibility != ActivityVisibility.PUBLIC
        or not profile_is_eligible_for_activity(actor, journey.activity)
    ):
        return False
    return True


class PersonalCommerceCheckoutAPIView(APIView):
    """Browse eligible offers and create at most one active order per Journey."""
    permission_classes = [IsAuthenticated]

    def get(self, request, journey_id):
        journey = _journey_for_actor(request.user, journey_id)
        order = _active_order(journey)
        allowed = _allowed_to_checkout(request.user, journey)
        offers = []
        if allowed and order is None:
            for offer in _checkout_offers(journey):
                if not offer.is_currently_available():
                    continue
                offers.append({
                    "id": str(offer.pk),
                    "label": offer.name,
                    "description": offer.description,
                    "unit_price": str(offer.unit_price),
                    "currency": offer.currency,
                    "min_quantity": offer.min_quantity,
                    "max_quantity": offer.max_quantity,
                    "payment_modes": list(offer.allowed_payment_modes),
                    "default_payment_mode": offer.payment_mode,
                    "occurrence_id": str(offer.occurrence_id) if offer.occurrence_id else None,
                })
        response = Response({
            "journey_id": str(journey.pk),
            "activity": {"id": str(journey.activity_id), "title": journey.activity.title},
            "can_order": allowed and order is None and bool(offers),
            "existing_order": _order_payload(order) if order else None,
            "offers": offers,
        })
        response["Cache-Control"] = "private, no-store"
        return response

    @transaction.atomic
    def post(self, request, journey_id):
        values = CommerceCheckoutInput(data=request.data)
        values.is_valid(raise_exception=True)
        data = values.validated_data
        journey = _journey_for_actor(request.user, journey_id, lock=True)
        if not _allowed_to_checkout(request.user, journey):
            raise ValidationError({"journey": "Cette démarche ne permet pas cette commande."})

        key = data["idempotency_key"].strip()
        existing_by_key = CommerceOrder.objects.filter(idempotency_key=key).first()
        if existing_by_key is not None:
            lines = list(existing_by_key.items.values("offer_id", "quantity"))
            if (
                existing_by_key.journey_id != journey.pk
                or existing_by_key.buyer_id != request.user.pk
                or existing_by_key.payment_mode != data["payment_mode"]
                or len(lines) != 1
                or lines[0]["offer_id"] != data["offer_id"]
                or lines[0]["quantity"] != data["quantity"]
            ):
                raise ValidationError({"idempotency_key": "Cette référence concerne une autre demande."})
            response = Response(_order_payload(existing_by_key), status=status.HTTP_200_OK)
            response["Cache-Control"] = "private, no-store"
            return response

        active = _active_order(journey)
        if active is not None:
            response = Response({
                "detail": "Une commande existe déjà pour cette démarche.",
                "existing_order": _order_payload(active),
            }, status=status.HTTP_409_CONFLICT)
            response["Cache-Control"] = "private, no-store"
            return response

        offer = get_object_or_404(_checkout_offers(journey), pk=data["offer_id"])
        if not offer.is_currently_available() or not offer.allows_payment_mode(data["payment_mode"]):
            raise ValidationError({"offer_id": "Cette offre n’est plus disponible dans ces conditions."})
        try:
            order = create_order(
                journey=journey,
                buyer=request.user,
                selections=[{"offer": offer, "quantity": data["quantity"]}],
                payment_mode=data["payment_mode"],
                idempotency_key=key,
            )
            # A provider obligation is appropriate only for a payable mode.
            # Never equate on-site/later payment with an online payment.
            if (
                order.total > 0
                and order.payment_mode in {PaymentMode.UPFRONT, PaymentMode.AFTER_APPROVAL}
            ):
                create_commerce_payment_obligation(commerce_order=order, actor=request.user)
        except DomainValidationError as exc:
            raise ValidationError({"detail": exc.messages}) from exc
        response = Response(_order_payload(order), status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "private, no-store"
        return response
