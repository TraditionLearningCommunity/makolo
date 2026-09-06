from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from activities.models import OccurrencePlaceRole, OccurrenceTimingKind
from capacity.models import CapacityReservationStatus
from commerce.models import OfferStatus
from commerce.selectors import offer_applies_to_occurrence
from core.participant_presentation import ParticipantActivityState, resolve_participant_activity_state
from core.product_language import vertical_for, vocabulary_for
from journeys.models import WorkflowKind

from .candidate_identity import activity_candidate_key
from .card_contract import RepresentationPresentation
from .representation import resolve_activity_representation


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
    candidate_family: str
    candidate_key: str
    activity_id: str
    occurrence_id: str
    vertical: str
    vertical_label: str
    title: str
    summary: str
    space_name: str
    timing_kind: str
    start_date: Any
    start_time: Any
    end_date: Any
    end_time: Any
    start_at: Any
    end_at: Any
    timezone: str
    local_start: Any
    temporal_summary: str
    place: DiscoveryPlace | None
    distance_km: float | None
    price: DiscoveryPrice
    availability: DiscoveryAvailability
    participant: ParticipantActivityState
    cta_label: str | None
    cta_url: str | None
    url: str
    matching_occurrence_ids: tuple[str, ...] = ()
    matching_count: int = 1
    image_url: str | None = None
    eyebrow: str | None = None
    representation: RepresentationPresentation | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("representation", None)
        for key in ("start_date", "end_date"):
            value = payload[key]
            payload[key] = value.isoformat() if value else None
        for key in ("start_time", "end_time"):
            value = payload[key]
            payload[key] = value.isoformat() if value else None
        for key in ("start_at", "end_at", "local_start"):
            value = payload[key]
            payload[key] = value.isoformat() if value else None
        if payload["price"]["minimum"] is not None:
            payload["price"]["minimum"] = str(payload["price"]["minimum"])
        expires_at = payload["participant"].get("expires_at")
        if expires_at:
            payload["participant"]["expires_at"] = expires_at.isoformat()
        return payload

    def to_map_dict(self) -> dict[str, Any] | None:
        if self.place is None or self.place.latitude is None or self.place.longitude is None:
            return None
        return {
            "candidate_key": self.candidate_key,
            "activity_id": self.activity_id,
            "occurrence_id": self.occurrence_id,
            "vertical": self.vertical,
            "title": self.title,
            "timing_kind": self.timing_kind,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "start_at": self.start_at.isoformat() if self.start_at else None,
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
            "availability": {"state": self.availability.state, "label": self.availability.label},
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
    occurrence_offers = _prefetched(occurrence, "offers")
    activity_offers = getattr(occurrence.activity, "_discovery_activity_offers", None)
    if occurrence_offers is None or activity_offers is None:
        from commerce.selectors import applicable_offers

        return list(applicable_offers(occurrence=occurrence))
    by_id = {offer.pk: offer for offer in activity_offers}
    by_id.update({offer.pk: offer for offer in occurrence_offers})
    return [offer for offer in by_id.values() if offer_applies_to_occurrence(offer, occurrence)]


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
    return DiscoveryPrice(False, cheapest.unit_price, cheapest.currency, f"À partir de {_format_amount(cheapest.unit_price)} {cheapest.currency}")


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


def occurrence_temporal_summary(occurrence):
    day = occurrence.start_date
    if day is None:
        return "Date à confirmer"
    day_label = date_format(day, "D d M")
    if occurrence.timing_kind == OccurrenceTimingKind.DATE_ONLY:
        return f"{day_label} · Heure à confirmer"
    if occurrence.timing_kind == OccurrenceTimingKind.ALL_DAY:
        return f"{day_label} · Toute la journée"
    if occurrence.start_time is not None:
        return f"{day_label} · {occurrence.start_time.strftime('%H:%M')}"
    return day_label


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

    def can_present_offer(self, occurrence) -> bool:
        return True


class EventPresenter(BasePresenter):
    key = "event"

    def matches(self, occurrence) -> bool:
        try:
            return occurrence.activity.event_vertical is not None
        except Exception:
            return False

    def _event(self, occurrence):
        return occurrence.activity.event_vertical

    def _is_primary(self, occurrence) -> bool:
        primary = self._event(occurrence).primary_occurrence
        return primary is not None and primary.pk == occurrence.pk

    def url(self, occurrence) -> str:
        return reverse("events:detail", args=[self._event(occurrence).slug])

    def can_present_offer(self, occurrence) -> bool:
        return self._is_primary(occurrence)

    def cta(self, occurrence, *, price, availability) -> str:
        if not self._is_primary(occurrence) or availability.state == "sold_out" or price.minimum is None:
            return "Voir l’événement"
        workflow = WorkflowKind.REGISTRATION if price.is_free else WorkflowKind.PURCHASE
        return vocabulary_for(activity=occurrence.activity, workflow=workflow).primary_action


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


PRESENTERS = (TransportPresenter(), EventPresenter())
DEFAULT_PRESENTER = BasePresenter()


def presenter_for(occurrence):
    for presenter in PRESENTERS:
        if presenter.matches(occurrence):
            return presenter
    return DEFAULT_PRESENTER


def build_discovery_item(occurrence, *, distance_m=None, now=None, profile=None, participant_context=None) -> DiscoveryItem:
    now = now or timezone.now()
    presenter = presenter_for(occurrence)
    representation = resolve_activity_representation(activity=occurrence.activity, occurrence=occurrence)
    vocabulary = vocabulary_for(activity=occurrence.activity)
    place = presenter.primary_place(occurrence)
    price = price_presentation(occurrence, now=now) if presenter.can_present_offer(occurrence) else DiscoveryPrice(False, None, None, None)
    availability = availability_presentation(occurrence, now=now)
    local_start = occurrence.start_at.astimezone(ZoneInfo(occurrence.timezone)) if occurrence.start_at else None
    public_place = None
    if place is not None:
        public_place = DiscoveryPlace(
            id=str(place.pk),
            name=place.name,
            locality=place.locality,
            latitude=float(place.latitude) if place.latitude is not None else None,
            longitude=float(place.longitude) if place.longitude is not None else None,
        )
    detail_url = presenter.url(occurrence)
    public_cta = presenter.cta(occurrence, price=price, availability=availability)
    participant = resolve_participant_activity_state(
        profile=profile,
        activity=occurrence.activity,
        occurrence=occurrence,
        context=participant_context,
        availability_state=availability.state,
        availability_label=availability.label,
        acquisition_label=public_cta,
        acquisition_url=detail_url,
        detail_url=detail_url,
        now=now,
    )
    candidate_key = activity_candidate_key(occurrence.activity)
    return DiscoveryItem(
        candidate_family=candidate_key.family,
        candidate_key=str(candidate_key),
        activity_id=str(occurrence.activity_id),
        occurrence_id=str(occurrence.pk),
        vertical=vertical_for(occurrence.activity),
        vertical_label=vocabulary.activity_noun,
        title=occurrence.activity.title,
        summary=occurrence.activity.short_description or occurrence.activity.description[:220],
        space_name=occurrence.activity.operator_display_name,
        timing_kind=occurrence.timing_kind,
        start_date=occurrence.start_date,
        start_time=occurrence.start_time,
        end_date=occurrence.end_date,
        end_time=occurrence.end_time,
        start_at=occurrence.start_at,
        end_at=occurrence.end_at,
        timezone=occurrence.timezone,
        local_start=local_start,
        temporal_summary=occurrence_temporal_summary(occurrence),
        place=public_place,
        distance_km=round(float(distance_m) / 1000, 1) if distance_m is not None else None,
        price=price,
        availability=availability,
        participant=participant,
        cta_label=participant.primary_action,
        cta_url=participant.primary_url,
        url=detail_url,
        matching_occurrence_ids=(str(occurrence.pk),),
        image_url=representation.image_url,
        eyebrow=representation.eyebrow,
        representation=representation,
    )


def _aggregate_price(items):
    priced = [item for item in items if item.price.minimum is not None]
    if not priced:
        return DiscoveryPrice(False, None, None, None)
    currencies = {item.price.currency for item in priced}
    if len(currencies) != 1:
        return DiscoveryPrice(False, None, None, "Plusieurs tarifs")
    currency = next(iter(currencies))
    values = [item.price.minimum for item in priced]
    low, high = min(values), max(values)
    if high == Decimal("0.00"):
        return DiscoveryPrice(True, low, currency, "Gratuit")
    label = f"À partir de {_format_amount(low)} {currency}" if low == high else f"{_format_amount(low)}–{_format_amount(high)} {currency}"
    return DiscoveryPrice(low == Decimal("0.00"), low, currency, label)


def _aggregate_availability(items):
    available = [item for item in items if item.availability.state not in {"sold_out", "cancelled", "completed", "closed"}]
    if not available:
        return DiscoveryAvailability("sold_out", "Complet", 0)
    if len(items) == 1:
        return items[0].availability
    return DiscoveryAvailability("available", f"{len(available)} date{'s' if len(available) != 1 else ''} disponible{'s' if len(available) != 1 else ''}", None)


def _aggregate_temporal(items):
    if len(items) == 1:
        return items[0].temporal_summary
    dates = {item.start_date for item in items}
    exact_times = [item.start_time for item in items if item.timing_kind == OccurrenceTimingKind.EXACT and item.start_time]
    if len(dates) == 1 and len(exact_times) == len(items):
        times = ", ".join(value.strftime("%H:%M") for value in sorted(exact_times))
        return f"{date_format(next(iter(dates)), 'D d M')} · {times}"
    return f"{len(items)} dates · Prochaine {items[0].temporal_summary}"


def aggregate_discovery_items(items):
    """Group matching Occurrences by Activity before Discovery pagination."""
    grouped = {}
    order = []
    for item in items:
        if item.activity_id not in grouped:
            grouped[item.activity_id] = []
            order.append(item.activity_id)
        grouped[item.activity_id].append(item)
    results = []
    for activity_id in order:
        matches = grouped[activity_id]
        first = matches[0]
        label = first.cta_label
        if len(matches) > 1 and first.participant.participant_state == "none":
            label = {"transport": "Voir les départs", "event": "Voir les dates"}.get(first.vertical, "Voir les horaires")
        results.append(
            replace(
                first,
                candidate_family="activity",
                candidate_key=str(activity_candidate_key(activity_id)),
                price=_aggregate_price(matches),
                availability=_aggregate_availability(matches),
                temporal_summary=_aggregate_temporal(matches),
                cta_label=label,
                matching_occurrence_ids=tuple(item.occurrence_id for item in matches),
                matching_count=len(matches),
            )
        )
    return results
