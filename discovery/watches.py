from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date

from .intent import resolve_discovery_intent
from .search import (
    ALLOWED_PERIODS,
    ALLOWED_RADIUS_KM,
    MAX_DATE_RANGE_DAYS,
    MAX_TEXT_LENGTH,
    resolve_time_window,
    search_occurrences,
    search_timezone,
)
from .unified import public_service_discovery_items


WATCH_CRITERIA_KEYS = (
    "q", "place", "when", "period", "vertical", "price", "radius_km", "lat", "lon",
    "date", "date_from", "date_to", "ordering", "timezone",
)
WATCH_MEANINGFUL_KEYS = {"q", "place", "when", "period", "vertical", "price", "lat", "lon", "date", "date_from", "date_to"}
ALLOWED_WHEN = {"today", "tomorrow", "week", "weekend"}
ALLOWED_VERTICALS = {"event", "transport", "service", "other"}
ALLOWED_PRICES = {"free", "paid"}
ALLOWED_ORDERINGS = {"soon", "proximity"}
SERVICE_UNSUPPORTED_KEYS = {"place", "when", "period", "price", "lat", "lon", "date", "date_from", "date_to"}


@dataclass(frozen=True)
class WatchExecutionResult:
    items: list
    service_items: list
    timezone_name: str
    total: int
    nearby_active: bool


def normalize_watch_criteria(criteria) -> dict[str, str]:
    if not isinstance(criteria, dict):
        raise ValidationError("Les critères de Veille doivent être structurés.")
    unknown = sorted(set(criteria) - set(WATCH_CRITERIA_KEYS))
    if unknown:
        raise ValidationError(f"Critère de recherche non supporté : {', '.join(unknown)}.")
    normalized = {key: str(criteria.get(key) or "").strip() for key in WATCH_CRITERIA_KEYS}
    for key in ("when", "period", "vertical", "price", "ordering"):
        normalized[key] = normalized[key].lower()
    if len(normalized["q"]) > MAX_TEXT_LENGTH:
        raise ValidationError(f"La recherche texte est limitée à {MAX_TEXT_LENGTH} caractères.")
    if len(normalized["place"]) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Le lieu est limité à {MAX_TEXT_LENGTH} caractères.")
    if normalized["when"] and normalized["when"] not in ALLOWED_WHEN:
        raise ValidationError("Filtre temporel de Veille invalide.")
    if normalized["period"] and normalized["period"] not in ALLOWED_PERIODS:
        raise ValidationError("Période de journée de Veille invalide.")
    if normalized["vertical"] and normalized["vertical"] not in ALLOWED_VERTICALS:
        raise ValidationError("Type d’activité de Veille invalide.")
    if normalized["price"] and normalized["price"] not in ALLOWED_PRICES:
        raise ValidationError("Filtre de prix de Veille invalide.")
    if normalized["ordering"] and normalized["ordering"] not in ALLOWED_ORDERINGS:
        raise ValidationError("Tri de Veille invalide.")

    exact = parse_date(normalized["date"]) if normalized["date"] else None
    date_from = parse_date(normalized["date_from"]) if normalized["date_from"] else None
    date_to = parse_date(normalized["date_to"]) if normalized["date_to"] else None
    if normalized["date"] and exact is None:
        raise ValidationError("Date précise de Veille invalide.")
    if normalized["date_from"] and date_from is None:
        raise ValidationError("Date de début de Veille invalide.")
    if normalized["date_to"] and date_to is None:
        raise ValidationError("Date de fin de Veille invalide.")
    if normalized["date"] and (normalized["date_from"] or normalized["date_to"]):
        raise ValidationError("Choisissez une date précise ou une plage de dates, pas les deux.")
    if normalized["when"] and (normalized["date"] or normalized["date_from"] or normalized["date_to"]):
        raise ValidationError("Choisissez une période rapide ou des dates explicites, pas les deux.")
    if date_from and date_to and date_to < date_from:
        raise ValidationError("La date de fin doit être postérieure à la date de début.")
    if date_from and date_to and (date_to - date_from).days > MAX_DATE_RANGE_DAYS:
        raise ValidationError(f"La plage de dates est limitée à {MAX_DATE_RANGE_DAYS} jours.")

    lat, lon = normalized["lat"], normalized["lon"]
    if bool(lat) != bool(lon):
        raise ValidationError("Latitude et longitude doivent être fournies ensemble.")
    if lat and lon:
        try:
            lat_value = float(lat); lon_value = float(lon); radius = int(normalized["radius_km"] or 10)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Coordonnées ou rayon de Veille invalides.") from exc
        if not -90 <= lat_value <= 90 or not -180 <= lon_value <= 180:
            raise ValidationError("Coordonnées de Veille hors limites.")
        if radius not in ALLOWED_RADIUS_KM:
            raise ValidationError("Rayon invalide. Choisissez 5, 10, 25 ou 50 km.")
        normalized["radius_km"] = str(radius)
    else:
        normalized["radius_km"] = ""
        if normalized["ordering"] == "proximity":
            raise ValidationError("Le tri par proximité exige une position et un rayon.")

    if normalized["timezone"]:
        try:
            ZoneInfo(normalized["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationError("Timezone de Veille invalide.") from exc

    if normalized["vertical"] == "service":
        unsupported = [key for key in SERVICE_UNSUPPORTED_KEYS if normalized[key]]
        if normalized["ordering"] == "proximity": unsupported.append("ordering")
        if unsupported:
            raise ValidationError("La recherche Accompagnement n’exécute pas encore ces critères : " + ", ".join(sorted(set(unsupported))) + ".")

    zone = search_timezone(place_text=normalized["place"] or None, timezone_name=normalized["timezone"] or None)
    resolve_time_window(normalized, zone=zone)
    result = {key: value for key, value in normalized.items() if value}
    if not any(result.get(key) for key in WATCH_MEANINGFUL_KEYS):
        raise ValidationError("Une Veille doit contenir au moins un critère de recherche exécutable.")
    return result


def criteria_from_discovery_params(params) -> dict[str, str]:
    return normalize_watch_criteria(resolve_discovery_intent(params).to_search_params())


def watch_query_string(criteria) -> str:
    return urlencode(normalize_watch_criteria(criteria))


def suggest_watch_name(criteria) -> str:
    criteria = normalize_watch_criteria(criteria)
    if criteria.get("q"):
        return criteria["q"][:140]
    labels = {"event": "Événements", "transport": "Voyager", "service": "Accompagnement", "other": "Autres activités", "today": "Aujourd’hui", "tomorrow": "Demain", "week": "Cette semaine", "weekend": "Ce week-end", "free": "Gratuit", "paid": "Payant"}
    parts = [labels.get(criteria[key], criteria[key]) for key in ("vertical", "place", "when", "price") if criteria.get(key)]
    return (" · ".join(parts) or "Ma veille")[:140]


def execute_watch(criteria, *, profile=None, now=None) -> WatchExecutionResult:
    criteria = normalize_watch_criteria(criteria)
    vertical = criteria.get("vertical", "")
    if vertical == "service":
        occurrence_result = SimpleNamespace(items=[], timezone_name=settings.TIME_ZONE, total=0, nearby_active=False)
    else:
        occurrence_result = search_occurrences(criteria, profile=profile, now=now)
    service_items = public_service_discovery_items(criteria, profile=profile)
    return WatchExecutionResult(items=occurrence_result.items, service_items=service_items, timezone_name=occurrence_result.timezone_name, total=occurrence_result.total + len(service_items), nearby_active=occurrence_result.nearby_active)
