from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from geography.value_objects import GeoPoint


class TemporalState(str, Enum):
    UPCOMING = "upcoming"
    SOON = "soon"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"


class HazardClass(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class HazardSeverity(str, Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ActionWindow:
    opens_at: datetime | None = None
    recommended_at: datetime | None = None
    deadline: datetime | None = None
    closes_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ArrivalWindow:
    opens_at: datetime
    closes_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class TemporalContext:
    now: datetime
    starts_at: datetime
    ends_at: datetime | None
    timezone: str
    starts_in: timedelta
    ends_in: timedelta | None
    state: TemporalState
    arrival_window: ArrivalWindow | None = None
    presentation_deadline: datetime | None = None
    action_windows: tuple[ActionWindow, ...] = ()


@dataclass(frozen=True, slots=True)
class SpatialContext:
    place: Any | None
    zone: Any | None
    destination: GeoPoint | None
    origin: GeoPoint | None = None
    straight_line_distance_m: int | None = None
    distance_kind: str | None = None
    itinerary_url: str = ""


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    duration: timedelta
    distance_m: int | None
    estimated_arrival_at: datetime | None
    source: str
    observed_at: datetime
    expires_at: datetime | None = None
    confidence: str = ""

    def is_stale(self, now: datetime) -> bool:
        return bool(self.expires_at and self.expires_at <= now)


@dataclass(frozen=True, slots=True)
class TrafficSignal:
    level: str
    delay: timedelta | None
    source: str
    observed_at: datetime
    expires_at: datetime | None = None

    def is_stale(self, now: datetime) -> bool:
        return bool(self.expires_at and self.expires_at <= now)


@dataclass(frozen=True, slots=True)
class WeatherSignal:
    kind: str
    severity: HazardSeverity
    source: str
    observed_at: datetime
    expires_at: datetime | None = None
    summary: str = ""

    def is_stale(self, now: datetime) -> bool:
        return bool(self.expires_at and self.expires_at <= now)


@dataclass(frozen=True, slots=True)
class MobilityContext:
    origin: GeoPoint | None
    destination: GeoPoint | None
    route_estimate: RouteEstimate | None
    traffic_signal: TrafficSignal | None
    weather_signal: WeatherSignal | None
    target_arrival: datetime | None
    recommended_departure: datetime | None
    status: str
    observed_at: datetime
    itinerary_url: str = ""


@dataclass(frozen=True, slots=True)
class Hazard:
    key: str
    kind: str
    hazard_class: HazardClass
    severity: HazardSeverity
    audience: str
    summary: str
    observed_at: datetime
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    source: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ActionAdvice:
    kind: str
    priority: int
    reason_code: str
    summary: str
    observed_at: datetime
    action_url: str = ""
    source_key: str = ""


@dataclass(frozen=True, slots=True)
class LastMinuteOpportunity:
    activity: Any
    occurrence: Any
    available_quantity: int | None
    reasons: tuple[str, ...]
    distance_m: int | None = None
    starts_in: timedelta | None = None
