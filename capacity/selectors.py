from dataclasses import dataclass

from django.db.models import Q, Sum
from django.utils import timezone

from .models import CapacityPool, CapacityReservation, CapacityReservationStatus


@dataclass(frozen=True)
class CapacityAvailability:
    total: int | None
    held: int
    committed: int
    available: int | None

    @property
    def unlimited(self):
        return self.total is None

    @property
    def sold_out(self):
        return self.available == 0 if self.available is not None else False


def pools_for_activity(activity):
    return CapacityPool.objects.filter(activity=activity).select_related("activity", "occurrence").order_by("occurrence_id", "label", "id")


def pools_for_occurrence(occurrence):
    return CapacityPool.objects.filter(occurrence=occurrence).select_related("activity", "occurrence").order_by("label", "id")


def reservations_for_journey(journey):
    return CapacityReservation.objects.filter(journey=journey).select_related("pool", "pool__activity", "pool__occurrence").order_by("created_at", "id")


def active_holds(*, pool=None, now=None):
    now = now or timezone.now()
    qs = CapacityReservation.objects.filter(status=CapacityReservationStatus.HELD).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )
    if pool is not None:
        qs = qs.filter(pool=pool)
    return qs.select_related("pool", "journey").order_by("expires_at", "created_at", "id")


def committed_reservations(*, pool=None):
    qs = CapacityReservation.objects.filter(status=CapacityReservationStatus.COMMITTED)
    if pool is not None:
        qs = qs.filter(pool=pool)
    return qs.select_related("pool", "journey").order_by("created_at", "id")


def capacity_availability(pool, *, now=None):
    now = now or timezone.now()
    aggregate = CapacityReservation.objects.filter(pool=pool).aggregate(
        held=Sum(
            "quantity",
            filter=Q(status=CapacityReservationStatus.HELD)
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
        ),
        committed=Sum("quantity", filter=Q(status=CapacityReservationStatus.COMMITTED)),
    )
    held = aggregate["held"] or 0
    committed = aggregate["committed"] or 0
    total = pool.total_quantity
    available = None if total is None else max(total - held - committed, 0)
    return CapacityAvailability(total=total, held=held, committed=committed, available=available)


def available_quantity(pool, *, now=None):
    return capacity_availability(pool, now=now).available


def is_sold_out(pool, *, now=None):
    return capacity_availability(pool, now=now).sold_out
