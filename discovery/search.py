from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from activities.models import (
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrenceStatus,
)
from capacity.models import CapacityPool
from commerce.models import Offer
from core.participant_selectors import participant_state_context
from geography.models import Place, SpacePlace
from geography.selectors import nearby_places
from geography.value_objects import GeoPoint

from .presentation import build_discovery_item, primary_place_for


MAX_TEXT_LENGTH = 120
MAX_DATE_RANGE_DAYS = 120
MAX_CANDIDATES = 500
ALLOWED_RADIUS_KM = (5, 10, 25, 50)


@dataclass(frozen=True)
class DiscoverySearchResult:
    items: list
    timezone_name: str
    total: int
    nearby_active: bool


def _valid_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None


def search_timezone(*, place_text=None, timezone_name=None):
    if timezone_name:
        zone = _valid_zone(timezone_name)
        if zone is None:
            raise ValidationError("Timezone de recherche invalide.")
        return zone
    if place_text:
        value = place_text.strip()
        place = (
            Place.objects.filter(is_active=True)
            .filter(Q(name__iexact=value) | Q(locality__iexact=value))
            .exclude(timezone="")
            .order_by("name", "pk")
            .first()
        )
        if place:
            zone = _valid_zone(place.timezone)
            if zone:
                return zone
    current = timezone.get_current_timezone()
    if current:
        return current
    return ZoneInfo(settings.TIME_ZONE)


def _day_window(day, zone):
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start, start + timedelta(days=1)


def resolve_time_window(params, *, zone, now=None):
    now = now or timezone.now()
    local_today = now.astimezone(zone).date()
    preset = (params.get("when") or "upcoming").strip().lower()
    raw_exact = (params.get("date") or "").strip()
    raw_from = (params.get("date_from") or "").strip()
    raw_to = (params.get("date_to") or "").strip()
    exact = parse_date(raw_exact)
    date_from = parse_date(raw_from)
    date_to = parse_date(raw_to)
    if raw_exact and exact is None:
        raise ValidationError("Date précise invalide.")
    if raw_from and date_from is None:
        raise ValidationError("Date de début invalide.")
    if raw_to and date_to is None:
        raise ValidationError("Date de fin invalide.")

    if exact:
        return _day_window(exact, zone)
    if date_from or date_to:
        first = date_from or local_today
        last = date_to or first
        if last < first:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")
        if (last - first).days > MAX_DATE_RANGE_DAYS:
            raise ValidationError(f"La plage de dates est limitée à {MAX_DATE_RANGE_DAYS} jours.")
        start = datetime.combine(first, time.min, tzinfo=zone)
        end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=zone)
        return start, end
    if preset == "today":
        return _day_window(local_today, zone)
    if preset == "tomorrow":
        return _day_window(local_today + timedelta(days=1), zone)
    if preset == "week":
        monday = local_today - timedelta(days=local_today.weekday())
        start = datetime.combine(monday, time.min, tzinfo=zone)
        return start, start + timedelta(days=7)
    if preset == "weekend":
        days_until_saturday = (5 - local_today.weekday()) % 7
        saturday = local_today + timedelta(days=days_until_saturday)
        if local_today.weekday() == 6:
            saturday = local_today - timedelta(days=1)
        start = datetime.combine(saturday, time.min, tzinfo=zone)
        return start, start + timedelta(days=2)
    if preset not in {"", "upcoming"}:
        raise ValidationError("Filtre temporel invalide.")
    return None


def _base_queryset(*, now):
    offers = Offer.objects.select_related("capacity_pool").prefetch_related("capacity_pool__reservations")
    pools = CapacityPool.objects.prefetch_related("reservations")
    space_places = SpacePlace.objects.select_related("place")
    return (
        Occurrence.objects.filter(
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
            status=OccurrenceStatus.SCHEDULED,
        )
        .filter(Q(end_at__gte=now) | Q(end_at__isnull=True, start_at__gte=now))
        .exclude(activity__space__verification_status="suspended")
        .select_related(
            "activity",
            "activity__space",
            "activity__owner_profile",
            "activity__event_vertical",
            "activity__event_vertical__category",
            "activity__transport_service",
            "activity__transport_service__route",
            "transport_departure",
        )
        .prefetch_related(
            "place_links__place",
            Prefetch("offers", queryset=offers),
            Prefetch("capacity_pools", queryset=pools),
            Prefetch("activity__space__space_places", queryset=space_places),
            "activity__transport_service__route__stops__place",
        )
        .order_by("start_at", "id")
    )


def _apply_time(queryset, window):
    if window is None:
        return queryset
    start, end = window
    return queryset.filter(start_at__lt=end).filter(
        Q(end_at__gt=start) | Q(end_at__isnull=True, start_at__gte=start)
    )


def _apply_text(queryset, text):
    if not text:
        return queryset
    return queryset.filter(
        Q(activity__title__icontains=text)
        | Q(activity__short_description__icontains=text)
        | Q(activity__description__icontains=text)
        | Q(activity__space__name__icontains=text)
        | Q(activity__owner_profile__first_name__icontains=text)
        | Q(activity__owner_profile__last_name__icontains=text)
        | Q(activity__owner_profile__username__icontains=text)
        | Q(place_links__place__name__icontains=text)
        | Q(place_links__place__locality__icontains=text)
    )


def _apply_place(queryset, place_text):
    if not place_text:
        return queryset
    return queryset.filter(
        Q(place_links__place__name__icontains=place_text)
        | Q(place_links__place__locality__icontains=place_text)
        | Q(place_links__place__administrative_area__icontains=place_text)
        | Q(
            activity__transport_service__route__stops__position=1,
            activity__transport_service__route__stops__place__locality__icontains=place_text,
        )
    )


def _apply_vertical(queryset, vertical):
    if not vertical:
        return queryset
    if vertical == "event":
        return queryset.filter(activity__event_vertical__isnull=False)
    if vertical == "transport":
        return queryset.filter(transport_departure__isnull=False)
    if vertical == "other":
        return queryset.filter(activity__event_vertical__isnull=True, transport_departure__isnull=True)
    raise ValidationError("Type d’activité invalide.")


def _parse_nearby(params):
    raw_lat = (params.get("lat") or "").strip()
    raw_lon = (params.get("lon") or "").strip()
    if not raw_lat and not raw_lon:
        return None
    if not raw_lat or not raw_lon:
        raise ValidationError("Latitude et longitude doivent être fournies ensemble.")
    try:
        lat = float(raw_lat)
        lon = float(raw_lon)
        radius = int(params.get("radius_km") or 10)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Coordonnées ou rayon invalides.") from exc
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValidationError("Coordonnées hors limites.")
    if radius not in ALLOWED_RADIUS_KM:
        raise ValidationError("Rayon invalide. Choisissez 5, 10, 25 ou 50 km.")
    point = GeoPoint(lat, lon)
    ranked = nearby_places(point, radius_m=radius * 1000, limit=MAX_CANDIDATES)
    return {place.pk: distance for place, distance in ranked}


def _text_rank(item, text):
    if not text:
        return 0
    needle = text.casefold()
    title = item.title.casefold()
    if title == needle:
        return 0
    if needle in title:
        return 1
    if item.place and (needle in item.place.name.casefold() or needle in item.place.locality.casefold()):
        return 2
    if needle in item.space_name.casefold():
        return 3
    return 4


def search_occurrences(params, *, profile=None, now=None):
    now = now or timezone.now()
    text = (params.get("q") or "").strip()
    place_text = (params.get("place") or params.get("city") or "").strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"La recherche texte est limitée à {MAX_TEXT_LENGTH} caractères.")
    if len(place_text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Le lieu est limité à {MAX_TEXT_LENGTH} caractères.")

    zone = search_timezone(
        place_text=place_text,
        timezone_name=(params.get("timezone") or "").strip() or None,
    )
    window = resolve_time_window(params, zone=zone, now=now)
    nearby = _parse_nearby(params)
    queryset = _base_queryset(now=now)
    queryset = _apply_time(queryset, window)
    queryset = _apply_text(queryset, text)
    queryset = _apply_place(queryset, place_text)
    queryset = _apply_vertical(queryset, (params.get("vertical") or "").strip().lower())
    if nearby is not None:
        queryset = queryset.filter(place_links__place_id__in=nearby.keys())

    occurrences = list(queryset.distinct()[:MAX_CANDIDATES])
    participant_context = participant_state_context(profile, occurrences)
    items = []
    for occurrence in occurrences:
        place = primary_place_for(occurrence)
        distance_m = (nearby or {}).get(place.pk) if nearby is not None and place is not None else None
        items.append(
            build_discovery_item(
                occurrence,
                distance_m=distance_m,
                now=now,
                profile=profile,
                participant_context=participant_context,
            )
        )

    price_filter = (params.get("price") or "").strip().lower()
    if price_filter == "free":
        items = [item for item in items if item.price.is_free]
    elif price_filter == "paid":
        items = [item for item in items if item.price.minimum is not None and not item.price.is_free]
    elif price_filter:
        raise ValidationError("Filtre de prix invalide.")

    ordering = (params.get("ordering") or "soon").strip().lower()
    if ordering == "proximity":
        if nearby is None:
            raise ValidationError("Le tri par proximité exige une position et un rayon.")
        items.sort(
            key=lambda item: (
                item.distance_km if item.distance_km is not None else float("inf"),
                item.start_at,
            )
        )
    elif ordering == "soon":
        items.sort(key=lambda item: (_text_rank(item, text), item.start_at, item.distance_km or 0))
    else:
        raise ValidationError("Tri invalide.")
    return DiscoverySearchResult(
        items=items,
        timezone_name=str(zone),
        total=len(items),
        nearby_active=nearby is not None,
    )


def get_public_occurrence(pk, *, now=None):
    now = now or timezone.now()
    return _base_queryset(now=now).get(pk=pk)
