"""Activity-level Commerce checkout, without a universal Journey start."""
from django.core.exceptions import ValidationError as DomainValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from commerce.models import CommerceOrder, Offer, PaymentMode
from commerce.selectors import currently_available_offers
from commerce.services import create_order, confirm_order
from events.models import Event
from groups.selectors import eligible_activity_ids_for_profile
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.services import create_journey
from organizations.models import SpaceLifecycle
from payments.obligation_services import create_commerce_payment_obligation

from .native_checkout_api import ACTIVE_ORDER_STATUSES, CommerceCheckoutInput, _order_payload


def public_activity_for_commerce(actor, activity_id, *, lock=False):
    qs = Activity.objects.filter(
        pk=activity_id, status=ActivityStatus.PUBLISHED,
        visibility=ActivityVisibility.PUBLIC,
    ).select_related("space", "owner_profile")
    if lock:
        qs = qs.select_for_update()
    activity = get_object_or_404(qs)
    if (
        activity.pk not in eligible_activity_ids_for_profile(actor, [activity.pk])
        or Event.objects.filter(activity=activity).exists()
    ):
        raise Http404
    if activity.space_id:
        space = activity.space
        visible = (
            space.public_profile and space.searchable
            and space.lifecycle == SpaceLifecycle.ACTIVE
            and space.verification_status != "suspended"
        )
    else:
        visible = UserProfile.objects.filter(
            user_id=activity.owner_profile_id,
            public_profile=True, searchable=True, user__is_active=True,
        ).exists()
    if not visible:
        raise Http404
    return activity


def activity_offer_choices(activity):
    """Published Offer, Occurrence and Capacity facts; never infer from price."""
    occurrences = list(
        Occurrence.objects.filter(
            activity=activity, status=OccurrenceStatus.SCHEDULED,
        ).order_by("start_at", "pk")[:50]
    )
    rows = []
    for occurrence in occurrences or [None]:
        for offer in currently_available_offers(
            activity=activity, occurrence=occurrence,
        ).prefetch_related("payment_options"):
            if not offer.is_currently_available:
                continue
            # after_approval requires a separately approved owner Journey.
            modes = [mode for mode in offer.allowed_payment_modes
                     if mode != PaymentMode.AFTER_APPROVAL]
            if not modes:
                continue
            rows.append({
                "id": str(offer.pk),
                "occurrence_id": str(occurrence.pk) if occurrence else None,
                "occurrence_label": (
                    occurrence.label or str(occurrence.start_at or "")
                    if occurrence else ""
                ),
                "label": offer.name,
                "unit_price": str(offer.unit_price),
                "currency": offer.currency,
                "min_quantity": offer.min_quantity,
                "max_quantity": offer.max_quantity,
                "payment_modes": modes,
                "default_payment_mode": offer.payment_mode if offer.payment_mode in modes else modes[0],
            })
    return rows


def active_activity_order(actor, activity):
    if not getattr(actor, "is_authenticated", False):
        return None
    return CommerceOrder.objects.filter(
        buyer=actor, journey__activity=activity,
        status__in=ACTIVE_ORDER_STATUSES,
    ).order_by("-created_at", "-pk").first()


class ActivityCommerceCheckoutAPIView(APIView):
    """Atomically create a Purchase Journey and owner-confirmed CommerceOrder."""
    permission_classes = [AllowAny]

    def get(self, request, activity_id):
        activity = public_activity_for_commerce(request.user, activity_id)
        existing = active_activity_order(request.user, activity)
        offers = activity_offer_choices(activity) if existing is None else []
        response = Response({
            "activity": {"id": str(activity.pk), "title": activity.title},
            "journey_id": None,
            "can_order": bool(offers),
            "existing_order": _order_payload(existing) if existing else None,
            "offers": offers,
        })
        response["Cache-Control"] = "private, no-store"
        return response

    @transaction.atomic
    def post(self, request, activity_id):
        if not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated()
        serializer = CommerceCheckoutInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        activity = public_activity_for_commerce(request.user, activity_id, lock=True)
        occurrence_id = data.get("occurrence_id")
        occurrence = (
            get_object_or_404(Occurrence, pk=occurrence_id, activity=activity,
                              status=OccurrenceStatus.SCHEDULED)
            if occurrence_id else None
        )
        key = data["idempotency_key"].strip()
        prior = CommerceOrder.objects.filter(idempotency_key=key).first()
        if prior is not None:
            lines = list(prior.items.values("offer_id", "quantity"))
            if (
                prior.buyer_id != request.user.pk
                or prior.journey.activity_id != activity.pk
                or prior.journey.occurrence_id != (occurrence.pk if occurrence else None)
                or prior.payment_mode != data["payment_mode"]
                or len(lines) != 1
                or lines[0]["offer_id"] != data["offer_id"]
                or lines[0]["quantity"] != data["quantity"]
            ):
                raise ValidationError({"idempotency_key": "Cette référence concerne une autre demande."})
            result = Response(_order_payload(prior))
            result["Cache-Control"] = "private, no-store"
            return result
        existing = active_activity_order(request.user, activity)
        if existing is not None:
            result = Response({
                "detail": "Une commande existe déjà.",
                "existing_order": _order_payload(existing),
            }, status=status.HTTP_409_CONFLICT)
            result["Cache-Control"] = "private, no-store"
            return result
        context_id = str(occurrence.pk) if occurrence else None
        matching = next((
            row for row in activity_offer_choices(activity)
            if row["id"] == str(data["offer_id"])
            and row["occurrence_id"] == context_id
            and data["payment_mode"] in row["payment_modes"]
        ), None)
        if matching is None:
            raise ValidationError({"offer_id": "Cette offre n’est plus disponible."})
        try:
            # An unfinished personal purchase Journey is the same domain
            # context, not a reason to create a duplicate one.
            journey = (
                Journey.objects.select_for_update(of=("self",))
                .filter(
                    initiated_by=request.user, beneficiary=request.user,
                    activity=activity, occurrence=occurrence,
                    workflow=WorkflowKind.PURCHASE,
                    status=JourneyStatus.DRAFT,
                )
                .order_by("-created_at", "-pk")
                .first()
            )
            if journey is None:
                journey = create_journey(
                    initiated_by=request.user, beneficiary=request.user,
                    activity=activity, occurrence=occurrence,
                    workflow=WorkflowKind.PURCHASE,
                )
            order = create_order(
                journey=journey, buyer=request.user,
                selections=[{"offer": Offer.objects.get(pk=data["offer_id"]),
                             "quantity": data["quantity"]}],
                payment_mode=data["payment_mode"],
                idempotency_key=key,
            )
            if order.total > 0 and order.payment_mode == PaymentMode.UPFRONT:
                create_commerce_payment_obligation(commerce_order=order, actor=request.user)
            if order.total == 0 and order.payment_mode == PaymentMode.NONE:
                confirm_order(order=order, actor=request.user)
        except DomainValidationError as exc:
            raise ValidationError({"detail": exc.messages}) from exc
        response = Response(_order_payload(order), status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "private, no-store"
        return response
