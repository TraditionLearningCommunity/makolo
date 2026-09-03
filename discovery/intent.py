from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from geography.models import Place


class ConstraintSource(str, Enum):
    EXPLICIT = "explicit"
    INTERPRETED = "interpreted"
    CONTEXTUAL = "contextual"
    DEFAULT = "default"


class DayPeriod(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


@dataclass(frozen=True)
class AppliedConstraint:
    key: str
    value: str
    label: str
    source: ConstraintSource


@dataclass(frozen=True)
class DiscoveryIntent:
    raw_text: str = ""
    text: str = ""
    vertical: str = ""
    place: str = ""
    when: str = ""
    period: str = ""
    price: str = ""
    radius_km: str = ""
    lat: str = ""
    lon: str = ""
    date: str = ""
    date_from: str = ""
    date_to: str = ""
    ordering: str = ""
    timezone: str = ""
    constraints: tuple[AppliedConstraint, ...] = field(default_factory=tuple)

    def to_search_params(self) -> dict[str, str]:
        values = {
            "q": self.text,
            "place": self.place,
            "when": self.when,
            "period": self.period,
            "vertical": self.vertical,
            "price": self.price,
            "radius_km": self.radius_km,
            "lat": self.lat,
            "lon": self.lon,
            "date": self.date,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "ordering": self.ordering,
            "timezone": self.timezone,
        }
        return {key: value for key, value in values.items() if value}


_WHEN_PATTERNS = (
    (re.compile(r"\b(?:aujourd['’]hui|ce jour)\b", re.IGNORECASE), "today", "Aujourd’hui"),
    (re.compile(r"\bdemain\b", re.IGNORECASE), "tomorrow", "Demain"),
    (re.compile(r"\b(?:ce\s+)?week[- ]?end\b", re.IGNORECASE), "weekend", "Week-end"),
)
_PERIOD_PATTERNS = (
    (re.compile(r"\bmatin(?:ee|ée)?\b", re.IGNORECASE), DayPeriod.MORNING.value, "Matin"),
    (re.compile(r"\bapr[eè]s[- ]?midi\b", re.IGNORECASE), DayPeriod.AFTERNOON.value, "Après-midi"),
    (re.compile(r"\b(?:ce\s+)?soir(?:ee|ée)?\b", re.IGNORECASE), DayPeriod.EVENING.value, "Soir"),
)
_VERTICAL_PATTERNS = (
    (re.compile(r"\b(?:voyager|voyage|trajet|transport|bus|depart|départ)\b", re.IGNORECASE), "transport", "Voyager"),
    (re.compile(r"\b(?:event|événement|evenement|concert|festival|sortie)\b", re.IGNORECASE), "event", "Événement"),
    (re.compile(r"\b(?:service|accompagnement|accompagner)\b", re.IGNORECASE), "service", "Service"),
)
_FREE_PATTERN = re.compile(r"\b(?:gratuit|gratuite|gratuitement)\b", re.IGNORECASE)
_NEARBY_PATTERN = re.compile(r"\b(?:autour de moi|près de moi|pres de moi|à proximité|a proximite)\b", re.IGNORECASE)


def _remove_match(text: str, match: re.Match[str]) -> str:
    return (text[: match.start()] + " " + text[match.end() :]).strip()


def _resolve_place(text: str):
    candidates = list(
        Place.objects.filter(is_active=True)
        .exclude(name="")
        .values_list("name", "locality")[:500]
    )
    values = set()
    for name, locality in candidates:
        for value in (name, locality):
            value = (value or "").strip()
            if value:
                values.add(value)
    for value in sorted(values, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return value, match
    return "", None


def intent_from_params(params: Mapping[str, str]) -> DiscoveryIntent:
    place = (params.get("place") or params.get("city") or "").strip()
    fields = {
        "raw_text": (params.get("q") or "").strip(),
        "text": (params.get("q") or "").strip(),
        "place": place,
        "when": (params.get("when") or "").strip().lower(),
        "period": (params.get("period") or "").strip().lower(),
        "vertical": (params.get("vertical") or "").strip().lower(),
        "price": (params.get("price") or "").strip().lower(),
        "radius_km": (params.get("radius_km") or "").strip(),
        "lat": (params.get("lat") or "").strip(),
        "lon": (params.get("lon") or "").strip(),
        "date": (params.get("date") or "").strip(),
        "date_from": (params.get("date_from") or "").strip(),
        "date_to": (params.get("date_to") or "").strip(),
        "ordering": (params.get("ordering") or "").strip().lower(),
        "timezone": (params.get("timezone") or "").strip(),
    }
    constraints = []
    labels = {
        "place": place,
        "when": fields["when"].title(),
        "period": fields["period"].title(),
        "vertical": fields["vertical"].title(),
        "price": fields["price"].title(),
    }
    for key in ("vertical", "place", "when", "period", "price"):
        if fields[key]:
            constraints.append(AppliedConstraint(key, fields[key], labels[key], ConstraintSource.EXPLICIT))
    return DiscoveryIntent(**fields, constraints=tuple(constraints))


def interpret_discovery_text(raw_text: str, *, base: DiscoveryIntent | None = None) -> DiscoveryIntent:
    raw_text = (raw_text or "").strip()
    intent = base or DiscoveryIntent()
    text = raw_text
    constraints = list(intent.constraints)
    explicit_count = len(constraints)
    values = {
        "vertical": intent.vertical,
        "place": intent.place,
        "when": intent.when,
        "period": intent.period,
        "price": intent.price,
    }

    if not values["vertical"]:
        for pattern, value, label in _VERTICAL_PATTERNS:
            match = pattern.search(text)
            if match:
                values["vertical"] = value
                constraints.append(AppliedConstraint("vertical", value, label, ConstraintSource.INTERPRETED))
                text = _remove_match(text, match)
                break

    if not values["when"]:
        for pattern, value, label in _WHEN_PATTERNS:
            match = pattern.search(text)
            if match:
                values["when"] = value
                constraints.append(AppliedConstraint("when", value, label, ConstraintSource.INTERPRETED))
                text = _remove_match(text, match)
                break

    if not values["period"]:
        for pattern, value, label in _PERIOD_PATTERNS:
            match = pattern.search(text)
            if match:
                values["period"] = value
                constraints.append(AppliedConstraint("period", value, label, ConstraintSource.INTERPRETED))
                text = _remove_match(text, match)
                break

    if not values["price"]:
        match = _FREE_PATTERN.search(text)
        if match:
            values["price"] = "free"
            constraints.append(AppliedConstraint("price", "free", "Gratuit", ConstraintSource.INTERPRETED))
            text = _remove_match(text, match)

    if not values["place"]:
        place, match = _resolve_place(text)
        if match:
            values["place"] = place
            constraints.append(AppliedConstraint("place", place, place, ConstraintSource.INTERPRETED))
            text = _remove_match(text, match)

    lat = intent.lat
    lon = intent.lon
    radius_km = intent.radius_km
    match = _NEARBY_PATTERN.search(text)
    if match and lat and lon:
        radius_km = radius_km or "10"
        constraints.append(AppliedConstraint("nearby", radius_km, f"Autour de moi · {radius_km} km", ConstraintSource.INTERPRETED))
        text = _remove_match(text, match)

    interpreted_count = len(constraints) - explicit_count
    if explicit_count == 0 and interpreted_count < 2:
        return DiscoveryIntent(raw_text=raw_text, text=raw_text)

    # Keep all unresolved language as classic Discovery text instead of guessing.
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return DiscoveryIntent(
        raw_text=raw_text,
        text=text,
        vertical=values["vertical"],
        place=values["place"],
        when=values["when"],
        period=values["period"],
        price=values["price"],
        radius_km=radius_km,
        lat=lat,
        lon=lon,
        date=intent.date,
        date_from=intent.date_from,
        date_to=intent.date_to,
        ordering=intent.ordering,
        timezone=intent.timezone,
        constraints=tuple(constraints),
    )


def resolve_discovery_intent(params: Mapping[str, str]) -> DiscoveryIntent:
    base = intent_from_params(params)
    return interpret_discovery_text(base.raw_text, base=base)
