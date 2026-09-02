from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from urllib.parse import quote

from geography.models import Zone, ZoneType
from geography.value_objects import GeoPoint

from .types import SpatialContext


def straight_line_distance_m(origin: GeoPoint, destination: GeoPoint) -> int:
    """Haversine distance, explicitly not a routed distance."""
    lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
    lat2, lon2 = radians(destination.latitude), radians(destination.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(6_371_000 * 2 * asin(sqrt(a)))


def primary_place(occurrence):
    if occurrence is None:
        return None
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    return (primary or (links[0] if links else None)).place if links else None


def zone_for_place(place):
    if place is None:
        return None
    if place.locality:
        match = Zone.objects.filter(
            is_active=True,
            zone_type=ZoneType.ADMINISTRATIVE,
            country_code=place.country_code,
            locality__iexact=place.locality,
        ).order_by("name", "id").first()
        if match:
            return match
    if place.administrative_area:
        return Zone.objects.filter(
            is_active=True,
            zone_type=ZoneType.ADMINISTRATIVE,
            country_code=place.country_code,
            administrative_area__iexact=place.administrative_area,
        ).order_by("name", "id").first()
    return None


def itinerary_deep_link(destination: GeoPoint | None, *, origin: GeoPoint | None = None) -> str:
    if destination is None:
        return ""
    destination_pair = f"{destination.latitude:.6f},{destination.longitude:.6f}"
    if origin is not None:
        origin_pair = f"{origin.latitude:.6f},{origin.longitude:.6f}"
        route = quote(f"{origin_pair};{destination_pair}", safe="")
        return f"https://www.openstreetmap.org/directions?route={route}"
    return (
        "https://www.openstreetmap.org/"
        f"?mlat={destination.latitude:.6f}&mlon={destination.longitude:.6f}"
        f"#map=16/{destination.latitude:.6f}/{destination.longitude:.6f}"
    )


def get_spatial_context(occurrence, *, origin: GeoPoint | None = None) -> SpatialContext:
    place = primary_place(occurrence)
    destination = place.point if place else None
    distance = None
    if origin is not None and destination is not None:
        distance = straight_line_distance_m(origin, destination)
    return SpatialContext(
        place=place,
        zone=zone_for_place(place),
        destination=destination,
        origin=origin,
        straight_line_distance_m=distance,
        distance_kind="straight_line" if distance is not None else None,
        itinerary_url=itinerary_deep_link(destination, origin=origin),
    )
