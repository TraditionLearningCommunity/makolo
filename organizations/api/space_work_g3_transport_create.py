"""MT5 native Transport route, vehicle and departure authoring.

Composition only: Geography owns Places; Transport owns route/vehicle/departure;
Activity, Capacity and Offer are created by existing Transport services.
Never authorize from Group membership, a route ID or a cached actor.
"""
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from commerce.models import PaymentMode
from geography.models import SpacePlace
from organizations.models import SpaceArchetype
from subscriptions.entitlements import resolve_entitlement
from transport.models import TransportRoute, TransportService, Vehicle, VehicleType
from transport.services import (
    configure_transport_fare, create_transport_departure,
    create_transport_route, create_transport_service,
    create_transport_vehicle, publish_transport_departure,
)

from .workspace_projection import workspace_spaces


def _uuid(raw, field):
    try:
        return UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({field: "Identifiant invalide."})


def _positive_int(raw, field):
    if isinstance(raw, bool):
        raise ValidationError({field: "Quantité entière requise."})
    try:
        number = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({field: "Quantité entière requise."})
    if number < 1:
        raise ValidationError({field: "La quantité doit être positive."})
    return number


def _text(raw, field, *, limit=180, blank=True):
    if raw is None and blank:
        return ""
    if not isinstance(raw, str):
        raise ValidationError({field: "Texte invalide."})
    value = raw.strip()
    if len(value) > limit or (not blank and not value):
        raise ValidationError({field: "Valeur absente ou trop longue."})
    return value


def _timestamp(raw, timezone_name, field):
    value = parse_datetime(str(raw or ""))
    if value is None:
        raise ValidationError({field: "Date et heure exactes requises."})
    if timezone.is_naive(value):
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value


def _page(queryset, offset, serialize):
    limit = 60
    rows = list(queryset[offset:offset + limit + 1])
    return {
        "items": [serialize(row) for row in rows[:limit]],
        "offset": offset,
        "limit": limit,
        "has_more": len(rows) > limit,
        "coverage_state": (
            "partial" if offset or len(rows) > limit else "established"
        ),
    }


class SpaceG3TransportCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _reply(data, *, status=200):
        response = Response(data, status=status)
        response["Cache-Control"] = "private, no-store"
        return response

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if (
            space is None
            or space.archetype != SpaceArchetype.TRANSPORT_OPERATOR
            or (request.query_params.get("responsibility") or "all") != "all"
            or not has_direct_space_permission(
                request.user, space, PermissionCode.SPACE_ACTIVITIES_MANAGE,
            )
        ):
            raise NotFound()
        return space

    def get(self, request, slug):
        space = self._space(request, slug)
        offsets = {}
        for key in ("routes_offset", "vehicles_offset", "places_offset"):
            try:
                offset = int(request.query_params.get(key, "0"))
            except (TypeError, ValueError):
                raise ValidationError({key: "Décalage invalide."})
            if not 0 <= offset <= 10000:
                raise ValidationError({key: "Pagination invalide."})
            offsets[key] = offset
        routes = TransportRoute.objects.filter(
            space=space, active=True,
        ).prefetch_related("stops__place").order_by("name", "pk")
        vehicles = Vehicle.objects.filter(
            space=space, active=True,
        ).order_by("label", "pk")
        places = SpacePlace.objects.filter(
            organization=space, is_active=True, place__is_active=True,
        ).select_related("place").order_by("place__name", "pk")
        return self._reply({
            "space": {"id": str(space.pk), "slug": space.slug},
            "responsibility": "all",
            "capabilities": {
                "create_route": True,
                "create_vehicle": True,
                "create_departure": resolve_entitlement(
                    space, "activities.create",
                ).allowed,
            },
            "routes": _page(
                routes, offsets["routes_offset"],
                lambda row: {
                    "id": str(row.pk), "name": row.name,
                    "timezone": (
                        row.origin.timezone if row.origin else None
                    ),
                },
            ),
            "vehicles": _page(
                vehicles, offsets["vehicles_offset"],
                lambda row: {
                    "id": str(row.pk), "label": row.label,
                    "physical_capacity": row.passenger_capacity,
                },
            ),
            "places": _page(
                places, offsets["places_offset"],
                lambda row: {
                    "id": str(row.place_id),
                    "name": row.place.name,
                },
            ),
            "vehicle_types": list(VehicleType.choices),
        })

    @transaction.atomic
    def post(self, request, slug):
        space = self._space(request, slug)
        if not isinstance(request.data, dict):
            raise ValidationError({"body": "Objet attendu."})
        data = request.data
        if any(key in data for key in (
            "space", "organization", "owner_profile", "activity_id",
            "occurrence_id", "capacity_pool_id", "offer_id",
        )):
            raise ValidationError({"owner": "Ces informations ne peuvent pas être modifiées."})
        kind = data.get("kind")
        try:
            if kind == "route":
                origin_id = _uuid(data.get("origin"), "origin")
                destination_id = _uuid(data.get("destination"), "destination")
                if origin_id == destination_id:
                    raise ValidationError({
                        "destination": "Choisissez deux lieux distincts.",
                    })
                rows = SpacePlace.objects.filter(
                    organization=space, is_active=True,
                    place__is_active=True,
                    place_id__in=[origin_id, destination_id],
                ).select_related("place")
                places = {row.place_id: row.place for row in rows}
                if len(places) != 2:
                    raise ValidationError({"places": "Lieux indisponibles dans cet Espace."})
                name = _text(data.get("name"), "name", limit=180) or (
                    f"{places[origin_id].name} → {places[destination_id].name}"
                )
                route = create_transport_route(
                    space=space, name=name,
                    code=_text(data.get("code"), "code", limit=48),
                    stops=[places[origin_id], places[destination_id]],
                )
                result = {"kind": "transport_route", "id": str(route.pk)}
            elif kind == "vehicle":
                vehicle_type = data.get("vehicle_type") or VehicleType.BUS
                if vehicle_type not in VehicleType.values:
                    raise ValidationError({"vehicle_type": "Type de véhicule inconnu."})
                vehicle = create_transport_vehicle(
                    space=space,
                    label=_text(data.get("label"), "label", limit=180, blank=False),
                    registration=_text(data.get("registration"), "registration", limit=80),
                    passenger_capacity=_positive_int(
                        data.get("passenger_capacity"), "passenger_capacity",
                    ),
                    vehicle_type=vehicle_type,
                )
                result = {"kind": "vehicle", "id": str(vehicle.pk)}
            elif kind == "departure":
                if not resolve_entitlement(space, "activities.create").allowed:
                    raise NotFound()
                route = TransportRoute.objects.filter(
                    pk=_uuid(data.get("route"), "route"),
                    space=space, active=True,
                ).first()
                if route is None:
                    raise NotFound()
                vehicle = None
                if data.get("vehicle"):
                    vehicle = Vehicle.objects.filter(
                        pk=_uuid(data["vehicle"], "vehicle"),
                        space=space, active=True,
                    ).first()
                    if vehicle is None:
                        raise NotFound()
                tz_name = data.get("timezone")
                if not isinstance(tz_name, str) or len(tz_name) > 100:
                    raise ValidationError({"timezone": "Fuseau horaire requis."})
                try:
                    ZoneInfo(tz_name)
                except (ZoneInfoNotFoundError, ValueError):
                    raise ValidationError({"timezone": "Fuseau horaire inconnu."})
                start = _timestamp(data.get("start_at"), tz_name, "start_at")
                end = (
                    _timestamp(data["end_at"], tz_name, "end_at")
                    if data.get("end_at") else None
                )
                if end and end <= start:
                    raise ValidationError({"end_at": "L'arrivée doit suivre le départ."})
                total = _positive_int(data.get("capacity"), "capacity")
                try:
                    price = Decimal(str(data.get("unit_price", "")))
                except (InvalidOperation, ValueError):
                    raise ValidationError({"unit_price": "Montant invalide."})
                if not price.is_finite() or price < 0:
                    raise ValidationError({"unit_price": "Montant invalide."})
                currency = _text(
                    data.get("currency"), "currency", limit=3, blank=False,
                ).upper()
                if len(currency) != 3 or not currency.isalpha():
                    raise ValidationError({"currency": "Code de devise invalide."})
                mode = data.get("payment_mode") or PaymentMode.UPFRONT
                if mode not in {
                    PaymentMode.UPFRONT, PaymentMode.ON_SITE, PaymentMode.NONE,
                }:
                    raise ValidationError({"payment_mode": "Mode non autorisé en Transport."})
                service = TransportService.objects.filter(
                    route=route, activity__space=space,
                ).select_related("activity").order_by("pk").first()
                if service is None:
                    service = create_transport_service(
                        space=space, created_by=request.user,
                        route=route,
                        title=_text(data.get("title"), "title", limit=220) or route.name,
                    )
                departure = create_transport_departure(
                    service=service, start_at=start, end_at=end,
                    timezone_name=tz_name, vehicle=vehicle, capacity=total,
                    boarding_instructions=_text(
                        data.get("boarding_instructions"), "boarding_instructions",
                        limit=320,
                    ),
                    operational_reference=_text(
                        data.get("operational_reference"), "operational_reference",
                        limit=80,
                    ),
                )
                configure_transport_fare(
                    departure=departure,
                    name=_text(data.get("fare_name"), "fare_name", limit=180) or "Standard",
                    unit_price=price, currency=currency, payment_mode=mode,
                )
                if data.get("publish") is True:
                    publish_transport_departure(departure=departure)
                result = {
                    "kind": "occurrence",
                    "id": str(departure.occurrence_id),
                    "departure_id": str(departure.pk),
                    "state": departure.occurrence.status,
                }
            else:
                raise ValidationError({"kind": "Opération Transport inconnue."})
        except DjangoValidationError as exc:
            error = (
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
            raise ValidationError({"transport": error}) from exc
        return self._reply({
            "space": {"id": str(space.pk), "slug": space.slug},
            "responsibility": "all",
            "created": result,
        }, status=201)
