"""Human calendar markers for a Journey's real Occurrence.

This is display-only: neither Journey status nor Jour J/Live admission is
computed from the calendar difference.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone


def journey_day_label(occurrence, *, at: datetime | None = None) -> str | None:
    if occurrence is None or occurrence.start_date is None:
        return None
    try:
        calendar_zone = ZoneInfo(occurrence.timezone)
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return None
    now = at or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    days = (now.astimezone(calendar_zone).date() - occurrence.start_date).days
    if days == 0:
        return "Jour J"
    return f"Jour −{-days}" if days < 0 else f"Jour J +{days}"


def additional_place_details(place) -> str | None:
    if place is None:
        return None
    shown = (place.name or place.locality or "").strip().casefold()
    values = []
    for candidate in (place.address_line, place.locality):
        value = (candidate or "").strip()
        if not value or value.casefold() == shown:
            continue
        if value.casefold() not in {current.casefold() for current in values}:
            values.append(value)
    return " · ".join(values) if values else None
