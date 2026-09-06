from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from activities.models import OccurrenceStatus, OccurrenceTimingKind

from .types import ArrivalWindow, TemporalContext, TemporalState


def soon_threshold() -> timedelta:
    return timedelta(minutes=int(getattr(settings, "SPATIOTEMPORAL_SOON_THRESHOLD_MINUTES", 120)))


def _aware_now(now=None):
    value = now or timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def temporal_state(occurrence, *, now=None) -> TemporalState:
    now = _aware_now(now)
    if occurrence.status == OccurrenceStatus.CANCELLED:
        return TemporalState.CANCELLED

    zone = ZoneInfo(occurrence.timezone)
    local_today = now.astimezone(zone).date()

    if occurrence.start_at is None:
        if occurrence.start_date is None:
            return TemporalState.UPCOMING
        effective_end_date = occurrence.end_date or occurrence.start_date
        if effective_end_date < local_today:
            return TemporalState.ENDED
        if occurrence.timing_kind == OccurrenceTimingKind.ALL_DAY and occurrence.start_date <= local_today <= effective_end_date:
            return TemporalState.ACTIVE
        # Date-only deliberately never becomes SOON: Makolo does not know the
        # instant closely enough to produce countdown/leave-now semantics.
        return TemporalState.UPCOMING

    if occurrence.end_at and occurrence.end_at <= now:
        return TemporalState.ENDED
    if occurrence.start_at <= now and (occurrence.end_at is None or occurrence.end_at > now):
        return TemporalState.ACTIVE
    if occurrence.start_at <= now + soon_threshold():
        return TemporalState.SOON
    return TemporalState.UPCOMING


def get_temporal_context(
    occurrence,
    *,
    now=None,
    arrival_window: ArrivalWindow | None = None,
    presentation_deadline=None,
    action_windows=(),
) -> TemporalContext:
    now = _aware_now(now)
    ZoneInfo(occurrence.timezone)
    return TemporalContext(
        now=now,
        starts_at=occurrence.start_at,
        ends_at=occurrence.end_at,
        timezone=occurrence.timezone,
        starts_in=(occurrence.start_at - now) if occurrence.start_at else None,
        ends_in=(occurrence.end_at - now) if occurrence.end_at else None,
        state=temporal_state(occurrence, now=now),
        arrival_window=arrival_window if occurrence.start_at else None,
        presentation_deadline=presentation_deadline,
        action_windows=tuple(action_windows),
    )
