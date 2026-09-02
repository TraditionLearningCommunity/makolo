from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from geography.value_objects import GeoPoint

from .types import RouteEstimate, TrafficSignal, WeatherSignal


class ProviderUnavailable(RuntimeError):
    pass


class RoutingProvider(ABC):
    key = "routing"

    @abstractmethod
    def estimate_route(
        self,
        *,
        origin: GeoPoint,
        destination: GeoPoint,
        departure_at: datetime,
    ) -> RouteEstimate | None:
        raise NotImplementedError


class TrafficProvider(ABC):
    key = "traffic"

    @abstractmethod
    def traffic_context(self, *, route: RouteEstimate, observed_at: datetime) -> TrafficSignal | None:
        raise NotImplementedError


class WeatherProvider(ABC):
    key = "weather"

    @abstractmethod
    def weather_context(self, *, place, at: datetime, observed_at: datetime) -> WeatherSignal | None:
        raise NotImplementedError


class NoOpRoutingProvider(RoutingProvider):
    key = "noop"

    def estimate_route(self, *, origin, destination, departure_at):
        return None


class NoOpTrafficProvider(TrafficProvider):
    key = "noop"

    def traffic_context(self, *, route, observed_at):
        return None


class NoOpWeatherProvider(WeatherProvider):
    key = "noop"

    def weather_context(self, *, place, at, observed_at):
        return None


@dataclass(slots=True)
class ProviderRegistry:
    routing: RoutingProvider
    traffic: TrafficProvider
    weather: WeatherProvider


_default_registry = ProviderRegistry(
    routing=NoOpRoutingProvider(),
    traffic=NoOpTrafficProvider(),
    weather=NoOpWeatherProvider(),
)


def get_provider_registry() -> ProviderRegistry:
    return _default_registry


def set_provider_registry(registry: ProviderRegistry) -> None:
    global _default_registry
    _default_registry = registry


def reset_provider_registry() -> None:
    set_provider_registry(
        ProviderRegistry(
            routing=NoOpRoutingProvider(),
            traffic=NoOpTrafficProvider(),
            weather=NoOpWeatherProvider(),
        )
    )
