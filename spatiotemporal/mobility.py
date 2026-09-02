from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .providers import ProviderUnavailable, get_provider_registry
from .spatial import get_spatial_context
from .types import MobilityContext


def safety_buffer() -> timedelta:
    return timedelta(minutes=int(getattr(settings, "SPATIOTEMPORAL_SAFETY_BUFFER_MINUTES", 10)))


def recommended_departure(*, target_arrival, route_estimate, buffer=None):
    if target_arrival is None or route_estimate is None:
        return None
    return target_arrival - route_estimate.duration - (buffer if buffer is not None else safety_buffer())


def get_mobility_context(
    occurrence,
    *,
    origin=None,
    target_arrival=None,
    now=None,
    providers=None,
) -> MobilityContext:
    now = now or timezone.now()
    spatial = get_spatial_context(occurrence, origin=origin)
    destination = spatial.destination
    registry = providers or get_provider_registry()
    route = traffic = weather = None

    if origin is not None and destination is not None:
        try:
            route = registry.routing.estimate_route(
                origin=origin,
                destination=destination,
                departure_at=now,
            )
        except (ProviderUnavailable, TimeoutError, OSError):
            route = None
        if route is not None and route.is_stale(now):
            route = None

    if route is not None:
        try:
            traffic = registry.traffic.traffic_context(route=route, observed_at=now)
        except (ProviderUnavailable, TimeoutError, OSError):
            traffic = None
        if traffic is not None and traffic.is_stale(now):
            traffic = None

    if spatial.place is not None:
        try:
            weather = registry.weather.weather_context(
                place=spatial.place,
                at=target_arrival or occurrence.start_at,
                observed_at=now,
            )
        except (ProviderUnavailable, TimeoutError, OSError):
            weather = None
        if weather is not None and weather.is_stale(now):
            weather = None

    departure = recommended_departure(
        target_arrival=target_arrival,
        route_estimate=route,
    )
    if destination is None:
        status = "no_destination"
    elif origin is None:
        status = "destination_only"
    elif route is None:
        status = "routing_unavailable"
    elif departure is not None and now >= departure:
        status = "leave_now"
    else:
        status = "ready"

    return MobilityContext(
        origin=origin,
        destination=destination,
        route_estimate=route,
        traffic_signal=traffic,
        weather_signal=weather,
        target_arrival=target_arrival,
        recommended_departure=departure,
        status=status,
        observed_at=now,
        itinerary_url=spatial.itinerary_url,
    )
