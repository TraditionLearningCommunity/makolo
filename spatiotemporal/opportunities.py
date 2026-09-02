from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from capacity.models import CapacityReservation, CapacityReservationStatus
from capacity.selectors import capacity_availability
from groups.community_services import profile_is_eligible_for_activity
from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES

from .spatial import get_spatial_context
from .types import LastMinuteOpportunity


def opportunity_window() -> timedelta:
    return timedelta(hours=int(getattr(settings, "SPATIOTEMPORAL_LAST_MINUTE_WINDOW_HOURS", 6)))


def capacity_release_window() -> timedelta:
    return timedelta(hours=int(getattr(settings, "SPATIOTEMPORAL_CAPACITY_RELEASE_WINDOW_HOURS", 12)))


def _recent_release(pool, *, now):
    return CapacityReservation.objects.filter(
        pool=pool,
        status=CapacityReservationStatus.RELEASED,
        released_at__gte=now - capacity_release_window(),
    ).exists()


def _waitlist_priority(profile, occurrence):
    try:
        from tickets.models import TicketWaitlistEntry, WaitlistStatus
    except ImportError:
        return False
    event = getattr(occurrence.activity, "event_vertical", None)
    if event is None:
        return False
    return TicketWaitlistEntry.objects.filter(
        user=profile,
        status__in={WaitlistStatus.WAITING, WaitlistStatus.OFFERED},
        ticket_type__event=event,
    ).exists()


def get_last_minute_candidates(profile, *, origin=None, now=None, limit=30):
    if not getattr(profile, "is_authenticated", False):
        return []
    now = now or timezone.now()
    end = now + opportunity_window()
    joined_activity_ids = set(
        Journey.objects.filter(beneficiary=profile)
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .values_list("activity_id", flat=True)
    )
    occurrences = (
        Occurrence.objects.filter(
            status=OccurrenceStatus.SCHEDULED,
            start_at__gt=now,
            start_at__lte=end,
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
            capacity_pools__is_active=True,
        )
        .exclude(activity_id__in=joined_activity_ids)
        .select_related(
            "activity",
            "activity__space",
            "activity__event_vertical",
            "activity__service_details",
            "activity__transport_service",
        )
        .prefetch_related("place_links__place", "capacity_pools")
        .distinct()
        .order_by("start_at", "id")[: max(limit * 3, limit)]
    )

    rows = []
    for occurrence in occurrences:
        activity = occurrence.activity
        if not profile_is_eligible_for_activity(profile, activity):
            continue
        available = None
        released = False
        has_capacity = False
        for pool in occurrence.capacity_pools.all():
            availability = capacity_availability(pool, now=now)
            if availability.unlimited or (availability.available or 0) > 0:
                has_capacity = True
                available = availability.available if available is None else max(available or 0, availability.available or 0)
                released = released or _recent_release(pool, now=now)
        if not has_capacity:
            continue

        spatial = get_spatial_context(occurrence, origin=origin)
        starts_in = occurrence.start_at - now
        if (
            origin is not None
            and spatial.straight_line_distance_m is not None
            and starts_in <= timedelta(minutes=15)
            and spatial.straight_line_distance_m > int(getattr(settings, "SPATIOTEMPORAL_IMMINENT_MAX_DISTANCE_M", 10_000))
        ):
            continue

        reasons = []
        if released:
            reasons.append("capacity_released")
        if origin is not None and spatial.straight_line_distance_m is not None:
            if spatial.straight_line_distance_m <= int(getattr(settings, "SPATIOTEMPORAL_NEARBY_RADIUS_M", 15_000)):
                reasons.append("nearby_now")
        if _waitlist_priority(profile, occurrence):
            reasons.append("waitlist_priority")
        if not reasons:
            continue
        rows.append(LastMinuteOpportunity(
            activity=activity,
            occurrence=occurrence,
            available_quantity=available,
            reasons=tuple(reasons),
            distance_m=spatial.straight_line_distance_m,
            starts_in=starts_in,
        ))
        if len(rows) >= limit:
            break
    return rows


def recommendation_reason_map(profile, *, origin=None, now=None, limit=30):
    """M6 adapter consumed by the M5 Activity-first recommendation engine."""
    result = {}
    for opportunity in get_last_minute_candidates(profile, origin=origin, now=now, limit=limit):
        codes = result.setdefault(opportunity.activity.pk, set())
        codes.update(reason for reason in opportunity.reasons if reason in {"capacity_released", "nearby_now"})
    return result
