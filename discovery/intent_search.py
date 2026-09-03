from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

from .intent import DayPeriod, DiscoveryIntent, resolve_discovery_intent
from .search import DiscoverySearchResult, search_occurrences


_PERIOD_WINDOWS = {
    DayPeriod.MORNING.value: (time(5, 0), time(12, 0)),
    DayPeriod.AFTERNOON.value: (time(12, 0), time(18, 0)),
    DayPeriod.EVENING.value: (time(18, 0), time.max),
}


def _apply_period(result: DiscoverySearchResult, intent: DiscoveryIntent) -> DiscoverySearchResult:
    if not intent.period:
        return result
    window = _PERIOD_WINDOWS.get(intent.period)
    if window is None:
        raise ValidationError("Période de journée invalide.")
    start, end = window
    zone = ZoneInfo(result.timezone_name)
    items = []
    for item in result.items:
        local_start = item.start_at.astimezone(zone) if item.start_at.tzinfo is not None else item.start_at
        local_time = local_start.time().replace(tzinfo=None)
        if start <= local_time <= end:
            items.append(item)
    return DiscoverySearchResult(
        items=items,
        timezone_name=result.timezone_name,
        total=len(items),
        nearby_active=result.nearby_active,
    )


def search_discovery_intent(intent: DiscoveryIntent, *, profile=None, now=None) -> DiscoverySearchResult:
    params = intent.to_search_params()
    params.pop("period", None)
    result = search_occurrences(params, profile=profile, now=now)
    return _apply_period(result, intent)


def resolve_and_search(params, *, profile=None, now=None):
    intent = resolve_discovery_intent(params)
    result = search_discovery_intent(intent, profile=profile, now=now)
    return intent, result
