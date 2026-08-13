from math import cos, radians

from django.db.models import Q

from .distance import haversine_distance_meters
from .models import Place, SpacePlace
from .value_objects import GeoPoint


METERS_PER_DEGREE_LATITUDE = 111_320.0
DEFAULT_NEARBY_CANDIDATE_LIMIT = 1000


def active_space_places(organization):
    return (
        SpacePlace.objects.filter(organization=organization, is_active=True, place__is_active=True)
        .select_related("place")
        .order_by("position", "role", "place__name")
    )


def places_in_locality(locality):
    return Place.objects.filter(is_active=True, locality__iexact=(locality or "").strip())


def places_in_country(country_code):
    return Place.objects.filter(is_active=True, country_code=(country_code or "").strip().upper())


def places_in_bounding_box(*, south, west, north, east):
    south = float(south)
    west = float(west)
    north = float(north)
    east = float(east)
    if not -90 <= south <= north <= 90:
        raise ValueError("La bounding box doit respecter -90 <= south <= north <= 90.")
    if not -180 <= west <= 180 or not -180 <= east <= 180:
        raise ValueError("Les longitudes de bounding box doivent être entre -180 et 180.")

    queryset = Place.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=south,
        latitude__lte=north,
    )
    if west <= east:
        return queryset.filter(longitude__gte=west, longitude__lte=east)
    return queryset.filter(Q(longitude__gte=west) | Q(longitude__lte=east))


def bounding_box_for_radius(point: GeoPoint, radius_m):
    radius_m = float(radius_m)
    if radius_m <= 0:
        raise ValueError("Le rayon doit être strictement positif.")
    lat_delta = radius_m / METERS_PER_DEGREE_LATITUDE
    cosine = abs(cos(radians(point.latitude)))
    lon_delta = 180.0 if cosine < 1e-12 else min(180.0, radius_m / (METERS_PER_DEGREE_LATITUDE * cosine))
    south = max(-90.0, point.latitude - lat_delta)
    north = min(90.0, point.latitude + lat_delta)
    west = point.longitude - lon_delta
    east = point.longitude + lon_delta
    if west < -180:
        west += 360
    if east > 180:
        east -= 360
    return south, west, north, east


def nearby_places(point: GeoPoint, *, radius_m, limit=50, candidate_limit=DEFAULT_NEARBY_CANDIDATE_LIMIT):
    if limit <= 0 or candidate_limit <= 0:
        return []
    south, west, north, east = bounding_box_for_radius(point, radius_m)
    candidates = list(
        places_in_bounding_box(south=south, west=west, north=north, east=east)
        .order_by("pk")[:candidate_limit]
    )
    ranked = []
    for place in candidates:
        distance = haversine_distance_meters(point, place.point)
        if distance <= radius_m:
            ranked.append((place, distance))
    ranked.sort(key=lambda item: item[1])
    return ranked[:limit]


def distance_between_places(origin, destination):
    if origin.point is None or destination.point is None:
        return None
    return haversine_distance_meters(origin.point, destination.point)
