from math import asin, cos, radians, sin, sqrt

from .value_objects import GeoPoint


EARTH_RADIUS_METERS = 6_371_008.8


def haversine_distance_meters(origin: GeoPoint, destination: GeoPoint) -> float:
    """Return the great-circle distance between two WGS84 points in meters."""
    lat1 = radians(origin.latitude)
    lat2 = radians(destination.latitude)
    delta_lat = radians(destination.latitude - origin.latitude)
    delta_lon = radians(destination.longitude - origin.longitude)
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(min(1.0, sqrt(haversine)))
