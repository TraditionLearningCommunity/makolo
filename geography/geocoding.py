from typing import Protocol

from .value_objects import GeoPoint


class Geocoder(Protocol):
    """Optional provider contract; geography core has no network implementation."""

    def geocode(self, address: str) -> GeoPoint | None:
        ...

    def reverse_geocode(self, point: GeoPoint) -> str | None:
        ...
