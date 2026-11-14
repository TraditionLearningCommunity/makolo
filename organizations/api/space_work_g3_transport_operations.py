"""MT5 Transport departure operations, delegated to canonical Transport services.

A selected Occurrence is not a Fleet authority. We validate the live Work
owner and Activity Operations permission on every read and command. Route,
vehicle, capacity and access remain owned by their existing domains.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from organizations.models import SpaceArchetype
from transport.models import TransportDeparture, Vehicle
from transport.selectors import departure_capacity_snapshot
from transport.services import (
    assign_vehicle, cancel_transport_departure,
    reschedule_transport_departure,
)

from .space_work_g3_transport_create import _timestamp, _text, _uuid
from .space_work_projection import build_space_work_projection
from .workspace_projection import workspace_spaces


TERMINAL = {
    OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED,
}


def transport_departure_owner(*, profile, space, responsibility, departure_id):
    """Never infer a departure from a free-floating Occurrence/Vehicle ID."""
    departure = (
        TransportDeparture.objects.select_related(
            "occurrence__activity__transport_service__route",
            "vehicle", "passenger_capacity_pool",
        ).filter(
            pk=departure_id,
            occurrence__activity__space=space,
        ).first()
    )
    if departure is None or not can(
        profile, PermissionCode.ACTIVITY_OPERATIONS_MANAGE,
        activity=departure.occurrence.activity,
    ):
        raise NotFound()
    projection = build_space_work_projection(
        profile=profile, space=space, responsibility_key=responsibility,
        source_kind="occurrence", source_id=str(departure.occurrence_id),
    )
    selection = (projection or {}).get("selection") or {}
    if selection.get("source") != {
        "kind": "occurrence", "id": str(departure.occurrence_id),
    }:
        raise NotFound()
    return departure


def transport_departure_actions(profile, space, responsibility, departure):
    current = departure.occurrence.status not in TERMINAL
    fleet = (
        responsibility == "all" and
        has_direct_space_permission(
            profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE,
        )
    )
    return {
        "can_assign_vehicle": bool(current and fleet),
        "can_reschedule": bool(current),
        "can_cancel": bool(current),
    }


def perform_transport_departure_action(*, departure, actor, space,
                                       responsibility, data):
    actions = transport_departure_actions(actor, space, responsibility, departure)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Objet attendu."})
    action = data.get("action")
    if action == "assign_vehicle" and actions["can_assign_vehicle"]:
        vehicle_id = _uuid(data.get("vehicle"), "vehicle")
        vehicle = Vehicle.objects.filter(
            pk=vehicle_id, space=space, active=True,
        ).first()
        if vehicle is None:
            raise NotFound()
        assign_vehicle(departure=departure, vehicle=vehicle)
    elif action == "reschedule" and actions["can_reschedule"]:
        name = _text(
            data.get("timezone"), "timezone", limit=100, blank=False,
        )
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({"timezone": "Fuseau horaire inconnu."})
        start = _timestamp(data.get("start_at"), name, "start_at")
        end = (
            _timestamp(data.get("end_at"), name, "end_at")
            if data.get("end_at") else None
        )
        if end is not None and end <= start:
            raise ValidationError({"end_at": "L'arrivée doit suivre le départ."})
        reschedule_transport_departure(
            departure=departure, start_at=start,
            end_at=end, timezone_name=name,
        )
    elif action == "cancel" and actions["can_cancel"]:
        if data.get("confirmed") is not True:
            raise ValidationError({"confirmed": "Confirmation explicite requise."})
        cancel_transport_departure(departure=departure)
    else:
        raise ValidationError({"action": "Cette opération est indisponible."})


class SpaceG3TransportDepartureOperationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _owner(self, request, slug, departure_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None or space.archetype != SpaceArchetype.TRANSPORT_OPERATOR:
            raise NotFound()
        responsibility = (
            request.query_params.get("responsibility") or "all"
        ).strip() or "all"
        departure = transport_departure_owner(
            profile=request.user, space=space,
            responsibility=responsibility, departure_id=departure_id,
        )
        return space, responsibility, departure

    @staticmethod
    def _response(payload):
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response

    def _payload(self, request, space, responsibility, departure):
        actions = transport_departure_actions(
            request.user, space, responsibility, departure,
        )
        vehicles = []
        has_more = False
        if actions["can_assign_vehicle"]:
            try:
                offset = int(request.query_params.get("vehicles_offset", "0"))
            except (TypeError, ValueError):
                raise ValidationError({"vehicles_offset": "Décalage invalide."})
            if offset < 0 or offset > 10000:
                raise ValidationError({"vehicles_offset": "Décalage hors limites."})
            rows = list(Vehicle.objects.filter(
                space=space, active=True,
            ).order_by("label", "pk")[offset:offset + 61])
            vehicles = [
                {
                    "id": str(vehicle.pk), "label": vehicle.label,
                    "physical_capacity": vehicle.passenger_capacity,
                } for vehicle in rows[:60]
            ]
            has_more = len(rows) > 60
        else:
            offset = 0
        occurrence = departure.occurrence
        return {
            "space": {"id": str(space.pk), "slug": space.slug},
            "responsibility": responsibility,
            "owner": {
                "kind": "transport_departure",
                "id": str(departure.pk),
                "occurrence_id": str(occurrence.pk),
            },
            "title": occurrence.label or occurrence.activity.title,
            "status": occurrence.status,
            "timing": {
                "start_at": occurrence.start_at.isoformat()
                if occurrence.start_at else None,
                "end_at": occurrence.end_at.isoformat()
                if occurrence.end_at else None,
                "timezone": occurrence.timezone,
            },
            "vehicle": (
                {"id": str(departure.vehicle_id),
                 "label": departure.vehicle.label}
                if departure.vehicle_id else None
            ),
            "capacity": {
                **departure_capacity_snapshot(departure),
                "basis": "capacity_pool",
            },
            "actions": actions,
            "vehicles": {
                "items": vehicles, "offset": offset, "limit": 60,
                "has_more": has_more,
            },
        }

    def get(self, request, slug, departure_id):
        space, responsibility, departure = self._owner(
            request, slug, departure_id,
        )
        return self._response(
            self._payload(request, space, responsibility, departure)
        )

    @transaction.atomic
    def post(self, request, slug, departure_id):
        space, responsibility, departure = self._owner(
            request, slug, departure_id,
        )
        # Serialize mutually dependent owner commands before the domain
        # services acquire their own locks. No optimistic local state.
        departure = TransportDeparture.objects.select_for_update().get(
            pk=departure.pk,
        )
        try:
            perform_transport_departure_action(
                departure=departure, actor=request.user,
                space=space, responsibility=responsibility, data=request.data,
            )
        except DjangoValidationError as exc:
            value = (
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
            raise ValidationError({"departure": value}) from exc
        departure = TransportDeparture.objects.select_related(
            "occurrence__activity", "vehicle", "passenger_capacity_pool",
        ).get(pk=departure.pk)
        data = self._payload(request, space, responsibility, departure)
        data["confirmed_by_owner"] = True
        return self._response(data)
