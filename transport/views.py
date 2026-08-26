import uuid
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from access.models import Access
from commerce.models import CommerceOrder, Offer, PaymentMode
from geography.models import Place
from journeys.beneficiary_services import create_external_beneficiary
from payments.models import PaymentMethod, PaymentProvider
from payments.services import initiate_commerce_payment

from .models import TransportDeparture
from .selectors import departure_available_offers, departure_capacity_snapshot, search_departures
from .services import book_transport


def _search_places():
    return Place.objects.filter(
        transport_route_stops__route__active=True,
        is_active=True,
    ).distinct().order_by("locality", "name")


def _departure_or_404(pk):
    return get_object_or_404(
        TransportDeparture.objects.select_related(
            "occurrence__activity__space",
            "occurrence__activity__owner_profile",
            "occurrence__activity__transport_service__route",
            "vehicle",
            "passenger_capacity_pool",
        ).prefetch_related(
            "occurrence__activity__transport_service__route__stops__place",
            "occurrence__offers__payment_options",
        ),
        pk=pk,
    )


def _purchased_accesses(profile, departure):
    if not getattr(profile, "is_authenticated", False):
        return Access.objects.none()
    return (
        Access.objects.filter(
            occurrence=departure.occurrence,
            journey__commerce_orders__buyer=profile,
        )
        .select_related("beneficiary", "external_beneficiary", "journey")
        .distinct()
        .order_by("created_at", "id")
    )


class TransportSearchView(TemplateView):
    template_name = "transport/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["places"] = _search_places()
        context["results"] = []
        context["searched"] = False
        raw_origin = (self.request.GET.get("origin") or "").strip()
        raw_destination = (self.request.GET.get("destination") or "").strip()
        raw_date = (self.request.GET.get("date") or "").strip()
        context.update({"origin_value": raw_origin, "destination_value": raw_destination, "date_value": raw_date})
        if not (raw_origin and raw_destination and raw_date):
            return context
        context["searched"] = True
        try:
            travel_date = date.fromisoformat(raw_date)
            origin = Place.objects.get(pk=raw_origin, is_active=True)
            destination = Place.objects.get(pk=raw_destination, is_active=True)
        except (ValueError, Place.DoesNotExist):
            context["search_error"] = "Choisissez une origine, une destination et une date valides."
            return context
        if origin.pk == destination.pk:
            context["search_error"] = "Le départ et la destination doivent être différents."
            return context
        rows = []
        for departure in search_departures(origin=origin, destination=destination, date=travel_date):
            route = departure.occurrence.activity.transport_service.route
            stops = list(route.stops.all())
            if len(stops) < 2 or stops[0].place_id != origin.pk or stops[-1].place_id != destination.pk:
                continue
            capacity = departure_capacity_snapshot(departure)
            offers = departure_available_offers(departure)
            rows.append(
                {
                    "departure": departure,
                    "route": route,
                    "origin": origin,
                    "destination": destination,
                    "capacity": capacity,
                    "offers": offers,
                    "from_price": min((offer.unit_price for offer in offers), default=None),
                    "currency": offers[0].currency if offers else "",
                    "payment_modes": sorted({mode for offer in offers for mode in offer.allowed_payment_modes}),
                }
            )
        context["results"] = rows
        context["origin"] = origin
        context["destination"] = destination
        return context


class TransportDepartureDetailView(TemplateView):
    template_name = "transport/departure_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departure = _departure_or_404(self.kwargs["pk"])
        occurrence = departure.occurrence
        if occurrence.status not in {"scheduled", "cancelled"}:
            raise Http404
        route = occurrence.activity.transport_service.route
        purchased_accesses = _purchased_accesses(self.request.user, departure)
        context.update(
            {
                "departure": departure,
                "occurrence": occurrence,
                "route": route,
                "stops": route.stops.all(),
                "capacity": departure_capacity_snapshot(departure),
                "offers": departure_available_offers(departure) if occurrence.status == "scheduled" else [],
                "purchased_accesses": purchased_accesses,
                "purchased_access_count": purchased_accesses.count(),
            }
        )
        return context


class TransportBookView(LoginRequiredMixin, TemplateView):
    template_name = "transport/booking.html"
    login_url = "core:login"

    def _objects(self):
        departure = _departure_or_404(self.kwargs["departure_id"])
        offer = get_object_or_404(Offer.objects.prefetch_related("payment_options"), pk=self.kwargs["offer_id"])
        if offer.occurrence_id != departure.occurrence_id:
            raise Http404
        return departure, offer

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departure, offer = self._objects()
        context.update(
            {
                "departure": departure,
                "route": departure.occurrence.activity.transport_service.route,
                "offer": offer,
                "capacity": departure_capacity_snapshot(departure),
                "idempotency_key": uuid.uuid4().hex,
                "payment_modes": offer.allowed_payment_modes,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        departure, offer = self._objects()
        if departure_capacity_snapshot(departure)["sold_out"]:
            messages.error(request, "Ce départ est complet.")
            return redirect("transport:departure-detail", pk=departure.pk)
        idempotency_key = (request.POST.get("idempotency_key") or uuid.uuid4().hex)[:128]
        selected_mode = (request.POST.get("payment_mode") or offer.payment_mode).strip()
        holder_type = (request.POST.get("holder_type") or "self").strip()
        beneficiary = request.user
        external_beneficiary = None
        try:
            existing = CommerceOrder.objects.filter(idempotency_key=idempotency_key, buyer=request.user).first()
            if existing is None and holder_type == "guest":
                guest_name = (request.POST.get("guest_name") or "").strip()
                if not guest_name:
                    raise ValidationError("Indiquez le nom du voyageur invité.")
                beneficiary = None
                external_beneficiary = create_external_beneficiary(
                    created_by=request.user,
                    display_name=guest_name,
                    email=(request.POST.get("guest_email") or "").strip(),
                    phone=(request.POST.get("guest_phone") or "").strip(),
                )
            elif holder_type not in {"self", "guest"}:
                raise ValidationError("Type de bénéficiaire invalide.")

            result = book_transport(
                departure=departure,
                offer=offer,
                participant=request.user,
                beneficiary=beneficiary,
                external_beneficiary=external_beneficiary,
                payment_mode=selected_mode,
                idempotency_key=idempotency_key,
            )
            if result["payment_mode"] == PaymentMode.UPFRONT:
                if not getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
                    raise ValidationError("Le paiement en ligne n’est pas disponible dans cet environnement.")
                payment = initiate_commerce_payment(
                    commerce_order=result["order"],
                    actor=request.user,
                    provider=PaymentProvider.SANDBOX,
                    method=PaymentMethod.OTHER,
                    idempotency_key=f"transport-payment:{result['order'].pk}",
                )
                messages.success(request, "Votre place est maintenue pendant le paiement.")
                return redirect("payments:detail", pk=payment.pk)
            if result["payment_mode"] == PaymentMode.ON_SITE:
                messages.success(
                    request,
                    f"Réservation confirmée. {result['order'].total} {result['order'].currency} à payer sur place.",
                )
            else:
                messages.success(request, "Réservation confirmée. Aucun paiement requis.")
            return redirect("core:participant-access-detail", pk=result["access"].pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("transport:departure-detail", pk=departure.pk)
