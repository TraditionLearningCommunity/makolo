from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import TemplateView

from capacity.models import CapacityReservationStatus
from commerce.models import PaymentMode
from geography.models import SpacePlace
from organizations.console_views import SpaceConsoleMixin

from .models import TransportDeparture, TransportRoute, TransportService, Vehicle
from .selectors import (
    departure_capacity_snapshot,
    departure_manifest,
    departures_for_route,
    routes_for_space,
    upcoming_departures,
    vehicles_for_space,
)
from .services import (
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    create_transport_vehicle,
    publish_transport_departure,
)


def _aware_local(value, timezone_name):
    parsed = parse_datetime(value or "")
    if parsed is None:
        raise ValidationError("Date/heure invalide.")
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def _scoped_departures(console, space):
    queryset = TransportDeparture.objects.filter(occurrence__activity__space=space)
    if console.activity_ids is not None:
        queryset = queryset.filter(occurrence__activity_id__in=console.activity_ids)
    return queryset


class TransportConsoleView(SpaceConsoleMixin, TemplateView):
    template_name = "transport/console.html"
    module_key = "activities"
    page_title = "Transport"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        routes = routes_for_space(self.space)
        departures = upcoming_departures(space=self.space)
        if self.space_console.activity_ids is not None:
            departures = departures.filter(occurrence__activity_id__in=self.space_console.activity_ids)
            route_ids = departures.values_list(
                "occurrence__activity__transport_service__route_id", flat=True
            )
            routes = routes.filter(pk__in=route_ids)
            vehicles = Vehicle.objects.none()
        else:
            vehicles = vehicles_for_space(self.space)
        context.update(
            {
                "routes": routes,
                "departures": departures,
                "vehicles": vehicles,
                "space_places": SpacePlace.objects.filter(
                    organization=self.space,
                    is_active=True,
                    place__is_active=True,
                ).select_related("place"),
                "can_manage_transport": self.space_console.can_manage_activities,
            }
        )
        return context


class TransportConsoleRouteDetailView(SpaceConsoleMixin, TemplateView):
    template_name = "transport/console_route_detail.html"
    module_key = "activities"
    page_title = "Route Transport"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        routes = routes_for_space(self.space)
        if self.space_console.activity_ids is not None:
            allowed_route_ids = _scoped_departures(self.space_console, self.space).values_list(
                "occurrence__activity__transport_service__route_id", flat=True
            )
            routes = routes.filter(pk__in=allowed_route_ids)
        route = get_object_or_404(routes, pk=self.kwargs["route_id"])
        services = route.services.select_related("activity").filter(activity__space=self.space)
        if self.space_console.activity_ids is not None:
            services = services.filter(activity_id__in=self.space_console.activity_ids)
        context.update(
            {
                "route": route,
                "stops": route.stops.select_related("place").order_by("position", "id"),
                "services": services,
                "future_departures": departures_for_route(route).filter(
                    occurrence__activity_id__in=services.values_list("activity_id", flat=True)
                ),
            }
        )
        return context


class TransportConsoleDepartureDetailView(SpaceConsoleMixin, TemplateView):
    template_name = "transport/console_departure_detail.html"
    module_key = "activities"
    page_title = "Départ Transport"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departure = get_object_or_404(
            _scoped_departures(self.space_console, self.space).select_related(
                "occurrence__activity__transport_service__route",
                "vehicle",
                "passenger_capacity_pool",
            ).prefetch_related(
                "occurrence__activity__transport_service__route__stops__place",
                "occurrence__offers",
            ),
            pk=self.kwargs["departure_id"],
        )
        pool = departure.passenger_capacity_pool
        now = timezone.now()
        reservation_counts = pool.reservations.aggregate(
            held=Sum(
                "quantity",
                filter=Q(status=CapacityReservationStatus.HELD)
                & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
            ),
            committed=Sum(
                "quantity",
                filter=Q(status=CapacityReservationStatus.COMMITTED),
            ),
        )
        manifest = departure_manifest(departure)
        context.update(
            {
                "departure": departure,
                "route": departure.occurrence.activity.transport_service.route,
                "capacity": departure_capacity_snapshot(departure),
                "held_count": reservation_counts["held"] or 0,
                "committed_count": reservation_counts["committed"] or 0,
                "manifest": manifest,
                "traveler_count": len(manifest),
                "boarded_count": sum(1 for row in manifest if row["boarded"]),
                "not_boarded_count": sum(1 for row in manifest if not row["boarded"]),
            }
        )
        return context


class TransportConsoleCreateRouteView(SpaceConsoleMixin, View):
    module_key = "activities"

    def post(self, request, *args, **kwargs):
        if not self.space_console.can_manage_activities:
            raise PermissionDenied("Vous ne pouvez pas créer de Route dans cet Espace.")
        relations = SpacePlace.objects.filter(
            organization=self.space,
            is_active=True,
            place__is_active=True,
            place_id__in=[request.POST.get("origin"), request.POST.get("destination")],
        ).select_related("place")
        by_id = {str(item.place_id): item.place for item in relations}
        origin = by_id.get(request.POST.get("origin"))
        destination = by_id.get(request.POST.get("destination"))
        if origin is None or destination is None or origin.pk == destination.pk:
            messages.error(request, "Choisissez deux Lieux valides et distincts de cet Espace.")
            return redirect("organizations:console-transport", slug=self.space.slug)
        try:
            route = create_transport_route(
                space=self.space,
                name=(request.POST.get("name") or f"{origin.locality or origin.name} → {destination.locality or destination.name}"),
                code=request.POST.get("code") or "",
                stops=[origin, destination],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, f"Route {route.name} créée.")
        return redirect("organizations:console-transport", slug=self.space.slug)


class TransportConsoleCreateVehicleView(SpaceConsoleMixin, View):
    module_key = "activities"

    def post(self, request, *args, **kwargs):
        if not self.space_console.can_manage_activities:
            raise PermissionDenied("Vous ne pouvez pas gérer la flotte de cet Espace.")
        try:
            vehicle = create_transport_vehicle(
                space=self.space,
                label=request.POST.get("label") or "",
                registration=request.POST.get("registration") or "",
                vehicle_type=request.POST.get("vehicle_type") or "bus",
                passenger_capacity=int(request.POST.get("passenger_capacity") or 0),
            )
        except (ValueError, ValidationError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, f"Véhicule {vehicle.label} ajouté.")
        return redirect("organizations:console-transport", slug=self.space.slug)


class TransportConsoleCreateDepartureView(SpaceConsoleMixin, View):
    module_key = "activities"

    def post(self, request, *args, **kwargs):
        if not self.space_console.can_manage_activities:
            raise PermissionDenied("Vous ne pouvez pas créer de Départ dans cet Espace.")
        route = get_object_or_404(TransportRoute, pk=request.POST.get("route"), space=self.space)
        vehicle = None
        if request.POST.get("vehicle"):
            vehicle = get_object_or_404(Vehicle, pk=request.POST.get("vehicle"), space=self.space)
        timezone_name = request.POST.get("timezone") or "Africa/Lubumbashi"
        try:
            start_at = _aware_local(request.POST.get("start_at"), timezone_name)
            end_at = _aware_local(request.POST.get("end_at"), timezone_name) if request.POST.get("end_at") else None
            capacity = int(request.POST.get("capacity") or (vehicle.passenger_capacity if vehicle else 0))
            unit_price = Decimal(request.POST.get("unit_price") or "0")
        except (ValueError, InvalidOperation, ValidationError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("organizations:console-transport", slug=self.space.slug)
        service = TransportService.objects.filter(route=route, activity__space=self.space).select_related("activity").first()
        try:
            if service is None:
                service = create_transport_service(
                    space=self.space,
                    created_by=request.user,
                    route=route,
                    title=request.POST.get("title") or route.name,
                )
            departure = create_transport_departure(
                service=service,
                start_at=start_at,
                end_at=end_at,
                timezone_name=timezone_name,
                vehicle=vehicle,
                capacity=capacity,
                boarding_instructions=request.POST.get("boarding_instructions") or "",
                operational_reference=request.POST.get("operational_reference") or "",
            )
            configure_transport_fare(
                departure=departure,
                name=request.POST.get("fare_name") or "Standard",
                unit_price=unit_price,
                currency=(request.POST.get("currency") or "USD").upper(),
                payment_mode=request.POST.get("payment_mode") or PaymentMode.UPFRONT,
            )
            if request.POST.get("publish") == "1":
                publish_transport_departure(departure=departure)
        except ValidationError as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Départ créé et configuré." if request.POST.get("publish") != "1" else "Départ publié.")
        return redirect("organizations:console-transport", slug=self.space.slug)
