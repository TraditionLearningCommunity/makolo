from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class GeoPoint:
    latitude: float
    longitude: float

    def __post_init__(self):
        latitude = float(self.latitude)
        longitude = float(self.longitude)
        if not isfinite(latitude) or not -90 <= latitude <= 90:
            raise ValueError("La latitude doit être comprise entre -90 et 90.")
        if not isfinite(longitude) or not -180 <= longitude <= 180:
            raise ValueError("La longitude doit être comprise entre -180 et 180.")
        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)

    def as_dict(self):
        return {"latitude": self.latitude, "longitude": self.longitude}
