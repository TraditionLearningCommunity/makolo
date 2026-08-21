from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone

from activities.models import OccurrencePlaceRole
from capacity.models import CapacityReservationStatus
from commerce.models import OfferStatus
from core.product_language import vocabulary_for
from journeys.models import WorkflowKind


@dataclass(frozen=True)
class DiscoveryPlace:
    id: str
    name: str
    locality: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class DiscoveryPrice:
    is_free: bool
    minimum: Decimal | None
    currency: str | None
    label: str | None


@dataclass(frozen=True)
class DiscoveryAvailability:
    state: str
    label: str
    remaining: int | None


@dataclass(frozen=True)
class DiscoveryItem:
    activity_id: str
    occurrence_id: str
    vertical: str
    vertical_label: str
    title: str
    summary: str
    space_name: str
    start_at: Any
    end_at: Any
    timezone: str
    local_start: Any
    place: DiscoveryPlace | None
    distance_km: float | None
    price: DiscoveryPrice
    availability: DiscoveryAvailability
    cta_label: str
    url: str
    image_url: str | None = None
    eyebrow: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("start_at", "end_at", "local_start"):
            value = payload[key]
            payload[key] = value.isoformat() if value else None
        if payload["price"]["minimum"] is not None:
            payload["price"]["minimum"] = str(payload["price"]["minimum"])
        return payload

    def to_map_dict(self) -> dict[str, Any] | None:
        if self.place is None or self.place.latitude is None or self.place.longitude is None:
            return None
        return {
            "activity_id": self.activity_id,
            "occurrence_id": self.occurrence_id,
            "vertical": self.vertical,
            "title": self.title,
            "start_at": self.start_at.isoformat(),
            "timezone": self.timezone,
            "place": {
                "name": self.place.name,
                "locality": self.place.locality,
                "latitude": self.place.latitude,
                "longitude": self.place.longitude,
            },
            "distance_km": self.distance_km,
            "price": {
                "is_free": self.price.is_free,
                "minimum": str(self.price.minimum) if self.price.minimum is not None else None,
                "currency": self.price.currency,
                "label": self.price.label,
            },
            "availability": {
                "state": self.availability.state,
                "label": self.availability.label,
            },
            "cta_label": self.cta_label,
            "url": self.url,
        }


def _prefetched(iterable_owner, relation_name):
    cache = getattr(iterable_owner, "_prefetched_objects_cache", {})
    return cache.get(relation_name)


def _space_place_is_public(activity, place) -> bool:
    space = activity.space
    if space is None:
        return True
    links = _prefetched(space, "space_places")
    if links is None:
        links = list(space.space_places.filter(place=place, is_active=True))
    relevant = [link for link in links if link.place_id == place.pk and link.is_active]
    if not relevant:
        return True
    return any(link.is_public for link in relevant)


def primary_place_for(occurrence):
    links = _prefetched(occurrence, "place_links")
    if links is None:
        links = list(occurrence.place_links.select_related("place"))
    primary = next((link for link in links if link.role == OccurrencePlaceRole.PRIMARY), None)
    if primary is None or not primary.place.is_active:
        return None
    if not _space_place_is_public(occurrence.activity, primary.place):
        return None
    return primary.place


def _reservations_for_pool(pool):
    reservations = _prefetched(pool, "reservations")
    return reservations if reservations is not None else list(pool.reservations.all())


def _pool_remaining(pool, *, now):
    if not pool.is_active:
        return 0
    if pool.total_quantity is None:
        return None
    used = 0
    for reservation in _reservations_for_pool(pool):
        if reservation.status == CapacityReservationStatus.COMMITTED:
            used += reservation.quantity
        elif reservation.status == CapacityReservationStatus.HELD and (
            reservation.expires_at is None or reservation.expires_at > now
        ):
            used += reservation.quantity
    return max(pool.total_quantity - used, 0)


def _offers_for_occurrence(occurrence):
    offers = _prefetched(occurrence, "offers")
    return offers if offers is not None else list(occurrence.offers.select_related("capacity_pool"))


def active_offers(occurrence, *, now=None):
    now = now or timezone.now()
    rows = []
    for offer in _offers_for_occurrence(occurrence):
        if offer.status != OfferStatus.ACTIVE:
            continue
        if offer.available_from and now < offer.available_from:
            continue
        if offer.available_until and now >= offer.available_until:
            continue
        if offer.capacity_pool_id and _pool_remaining(offer.capacity_pool, now=now) == 0:
            continue
        rows.append(offer)
    return rows


def _format_amount(amount):
    normalized = amount.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def price_presentation(occurrence, *, now=None):
    offers = active_offers(occurrence, now=now)
    if not offers:
        return DiscoveryPrice(False, None, None, None)
    free = [offer for offer in offers if offer.unit_price == Decimal("0.00")]
    if free:
        return DiscoveryPrice(True, Decimal("0.00"), free[0].currency, "Gratuit")
    cheapest = min(offers, key=lambda offer: (offer.unit_price, offer.currency, str(offer.pk)))
    return DiscoveryPrice(
        False,
        cheapest.unit_price,
        cheapest.currency,
        f"À partir de {_format_amount(cheapest.unit_price)} {cheapest.currency}",
    )


def availability_presentation(occurrence, *, now=None):
    now = now or timezone.now()
    pools = _prefetched(occurrence, "capacity_pools")
    if pools is None:
        pools = list(occurrence.capacity_pools.filter(is_active=True).prefetch_related("reservations"))
    pools = [pool for pool in pools if pool.is_active]
    if not pools:
        return DiscoveryAvailability("available", "Disponible", None)
    remaining = [_pool_remaining(pool, now=now) for pool in pools]
    if any(value is None for value in remaining):
        return DiscoveryAvailability("unlimited", "Illimité", None)
    total_remaining = sum(remaining)
    if total_remaining <= 0:
        return DiscoveryAvailability("sold_out", "Complet", 0)
    return DiscoveryAvailability("available", "Disponible", total_remaining)


class BasePresenter:
    key = "other"

    def matches(self, occurrence) -> bool:
        return True

    def primary_place(self, occurrence):
        return primary_place_for(occurrence)

    def url(self, occurrence) -> str:
        return reverse("discovery:activity-detail", args=[occurrence.pk])

    def cta(self, occurrence, *, price, availability) -> str:
        return vocabulary_for(activity=occurrence.activity).primary_action

    def image_url(self, occurrence) -> str | None:
        return None

    def eyebrow(self, occurrence) -> str | None:
        return None


class EventPresenter(BasePresenter):
    key = "event"

    def matches(self, occurrence) -> bool:
        try:
            return occurrence.activity.event_vertical is not None
        except Exception:
            return False

    def _event(self, occurrence):
        return occurrence.activity.event_vertical

    def url(self, occurrence) -> str:
        return reverse("events:detail", args=[self._event(occurrence).slug])

    def cta(self, occurrence, *, price, availability) -> str:
        if availability.state == "sold_out" or price.minimum is None:
            return "Voir l’événement"
        workflow = WorkflowKind.REGISTRATION if price.is_free else WorkflowKind.PURCHASE
        return vocabulary_for(activity=occurrence.activity, workflow=workflow).primary_action

    def image_url(self, occurrence) -> str | None:
        image = self._event(occurrence).cover_image
        return image.url if image else None

    def eyebrow(self, occurrence) -> str | None:
        category = self._event(occurrence).category
        return category.name if category else None


class TransportPresenter(BasePresenter):
    key = "transport"

    def matches(self, occurrence) -> bool:
        try:
            return occurrence.transport_departure is not None
        except Exception:
            return False

    def _departure(self, occurrence):
        return occurrence.transport_departure

    def primary_place(self, occurrence):
        canonical = primary_place_for(occurrence)
        if canonical is not None:
            return canonical
        try:
            place = occurrence.activity.transport_service.route.origin
            if place is not None and _space_place_is_public(occurrence.activity, place):
                return place
        except Exception:
            pass
        return None

    def url(self, occurrence) -> str:
        return reverse("transport:departure-detail", args=[self._departure(occurrence).pk])

    def cta(self, occurrence, *, price, availability) -> str:
        if availability.state == "sold_out":
            return "Voir le départ"
        return vocabulary_for(activity=occurrence.activity, workflow=WorkflowKind.RESERVATION).primary_action

    def eyebrow(self, occurrence) -> str | None:
        try:
            route = occurrence.activity.transport_service.route
            origin = route.origin
            destination = route.destination
            if origin and destination:
                return f"{origin.locality or origin.name} → {destination.locality or destination.name}"
        except Exception:
            pass
        return "Départ"


PRESENTERS = (TransportPresenter(), EventPresenter())
DEFAULT_PRESENTER = BasePresenter()


def presenter_for(occurrence):
    for presenter in PRESENTERS:
        if presenter.matches(occurrence):
            return presenter
    return DEFAULT_PRESENTER


def build_discovery_item(occurrence, *, distance_m=None, now=None) -> DiscoveryItem:
    now = now or timezone.now()
    presenter = presenter_for(occurrence)
    vocabulary = vocabulary_for(activity=occurrence.activity)
    place = presenter.primary_place(occurrence)
    price = price_presentation(occurrence, now=now)
    availability = availability_presentation(occurrence, now=now)
    local_zone = ZoneInfo(occurrence.timezone)
    local_start = occurrence.start_at.astimezone(local_zone)
    public_place = None
    if place is not None:
        public_place = DiscoveryPlace(
            id=str(place.pk),
            name=place.name,
            locality=place.locality,
            latitude=float(place.latitude) if place.latitude is not None else None,
            longitude=float(place.longitude) if place.longitude is not None else None,
        )
    return DiscoveryItem(
        activity_id=str(occurrence.activity_id),
        occurrence_id=str(occurrence.pk),
        vertical=presenter.key,
        vertical_label=vocabulary.activity_noun,
        title=occurrence.activity.title,
        summary=occurrence.activity.short_description or occurrence.activity.description[:220],
        space_name=occurrence.activity.space.name if occurrence.activity.space_id else "",
        start_at=occurrence.start_at,
        end_at=occurrence.end_at,
        timezone=occurrence.timezone,
        local_start=local_start,
        place=public_place,
        distance_km=round(float(distance_m) / 1000, 1) if distance_m is not None else None,
        price=price,
        availability=availability,
        cta_label=presenter.cta(occurrence, price=price, availability=availability),
        url=presenter.url(occurrence),
        image_url=presenter.image_url(occurrence),
        eyebrow=presenter.eyebrow(occurrence),
    )
