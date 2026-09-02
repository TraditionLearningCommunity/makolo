from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from geography.value_objects import GeoPoint
from journeys.models import Journey

from .context import get_journey_spatiotemporal_context
from .opportunities import get_last_minute_candidates


def _origin_from_request(request):
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if lat in {None, ""} and lon in {None, ""}:
        return None
    if lat in {None, ""} or lon in {None, ""}:
        raise ValueError("Latitude et longitude doivent être fournies ensemble.")
    return GeoPoint(float(lat), float(lon))


def _serialize_point(point):
    return point.as_dict() if point is not None else None


def _serialize_context(context):
    if context is None:
        return {"available": False}
    occurrence = context["occurrence"]
    temporal = context["temporal"]
    spatial = context["spatial"]
    mobility = context["mobility"]
    return {
        "available": True,
        "occurrence": {
            "id": str(occurrence.pk),
            "activity_id": str(occurrence.activity_id),
        },
        "temporal": {
            "state": temporal.state.value,
            "now": temporal.now.isoformat(),
            "starts_at": temporal.starts_at.isoformat(),
            "ends_at": temporal.ends_at.isoformat() if temporal.ends_at else None,
            "timezone": temporal.timezone,
            "starts_in_seconds": round(temporal.starts_in.total_seconds()),
            "ends_in_seconds": round(temporal.ends_in.total_seconds()) if temporal.ends_in else None,
        },
        "spatial": {
            "place": (
                {
                    "id": str(spatial.place.pk),
                    "name": spatial.place.name,
                    "locality": spatial.place.locality,
                    "address_line": spatial.place.address_line,
                }
                if spatial.place else None
            ),
            "zone": {"id": str(spatial.zone.pk), "name": spatial.zone.name} if spatial.zone else None,
            "origin": _serialize_point(spatial.origin),
            "destination": _serialize_point(spatial.destination),
            "distance_m": spatial.straight_line_distance_m,
            "distance_kind": spatial.distance_kind,
            "itinerary_url": spatial.itinerary_url,
        },
        "mobility": {
            "status": mobility.status,
            "target_arrival": mobility.target_arrival.isoformat() if mobility.target_arrival else None,
            "recommended_departure": (
                mobility.recommended_departure.isoformat() if mobility.recommended_departure else None
            ),
            "route": (
                {
                    "duration_seconds": round(mobility.route_estimate.duration.total_seconds()),
                    "distance_m": mobility.route_estimate.distance_m,
                    "source": mobility.route_estimate.source,
                    "observed_at": mobility.route_estimate.observed_at.isoformat(),
                    "expires_at": (
                        mobility.route_estimate.expires_at.isoformat()
                        if mobility.route_estimate.expires_at else None
                    ),
                }
                if mobility.route_estimate else None
            ),
            "traffic": (
                {
                    "level": mobility.traffic_signal.level,
                    "source": mobility.traffic_signal.source,
                    "observed_at": mobility.traffic_signal.observed_at.isoformat(),
                }
                if mobility.traffic_signal else None
            ),
            "weather": (
                {
                    "kind": mobility.weather_signal.kind,
                    "severity": mobility.weather_signal.severity.value,
                    "summary": mobility.weather_signal.summary,
                    "source": mobility.weather_signal.source,
                    "observed_at": mobility.weather_signal.observed_at.isoformat(),
                }
                if mobility.weather_signal else None
            ),
        },
        "hazards": [
            {
                "key": hazard.key,
                "kind": hazard.kind,
                "class": hazard.hazard_class.value,
                "severity": hazard.severity.value,
                "audience": hazard.audience,
                "summary": hazard.summary,
                "observed_at": hazard.observed_at.isoformat(),
                "source": hazard.source,
            }
            for hazard in context["hazards"]
        ],
        "advices": [
            {
                "kind": advice.kind,
                "priority": advice.priority,
                "reason_code": advice.reason_code,
                "summary": advice.summary,
                "action_url": advice.action_url,
                "observed_at": advice.observed_at.isoformat(),
            }
            for advice in context["advices"]
        ],
    }


class JourneyContextAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, journey_id):
        journey = get_object_or_404(
            Journey.objects.filter(beneficiary=request.user)
            .select_related("activity", "occurrence")
            .prefetch_related(
                "occurrence__place_links__place",
                "steps__occurrence__place_links__place",
                "accesses",
            ),
            pk=journey_id,
        )
        try:
            origin = _origin_from_request(request)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Origine géographique invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_serialize_context(get_journey_spatiotemporal_context(journey, origin=origin)))


class LastMinuteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            origin = _origin_from_request(request)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Origine géographique invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = get_last_minute_candidates(request.user, origin=origin, limit=20)
        return Response({
            "results": [
                {
                    "activity_id": str(row.activity.pk),
                    "occurrence_id": str(row.occurrence.pk),
                    "title": row.activity.title,
                    "starts_at": row.occurrence.start_at.isoformat(),
                    "available_quantity": row.available_quantity,
                    "distance_m": row.distance_m,
                    "reasons": list(row.reasons),
                }
                for row in rows
            ]
        })
