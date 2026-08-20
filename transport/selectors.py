from datetime import datetime, time, timedelta

from django.db.models import OuterRef, Prefetch, Q, Subquery, Sum
from django.utils import timezone

from access.models import Access, AccessUseResult
from capacity.models import CapacityReservationStatus
from commerce.models import Offer, OfferStatus

from .models import TransportDeparture, TransportRoute, TransportRouteStop, Vehicle


def routes_for_space(space):
    return TransportRoute.objects.filter(space=space).prefetch_related("stops__place")


def vehicles_for_space(space):
    return Vehicle.objects.filter(space=space)


def _departure_qs():
    return (
        TransportDeparture.objects.select_related(
            "occurrence__activity__space",
            "occurrence__activity__transport_service__route",
            "vehicle",
            "passenger_capacity_pool",
        )
        .prefetch_related(
            "occurrence__activity__transport_service__route__stops__place",
            Prefetch(
                "occurrence__offers",
                queryset=Offer.objects.filter(status=OfferStatus.ACTIVE).order_by("unit_price", "name"),
            ),
        )
    )


def upcoming_departures(*, space=None, now=None):
    now = now or timezone.now()
    qs = _departure_qs().filter(
        occurrence__start_at__gt=now,
        occurrence__status="scheduled",
        occurrence__activity__status="published",
        occurrence__activity__transport_service__route__active=True,
    )
    return qs.filter(occurrence__activity__space=space) if space else qs


def departures_for_route(route, *, now=None):
    return upcoming_departures(space=route.space, now=now).filter(
        occurrence__activity__transport_service__route=route
    )


def search_departures(*, origin, destination, date):
    local_zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date, time.min), local_zone)
    end = start + timedelta(days=1)
    last_place = (
        TransportRouteStop.objects.filter(
            route_id=OuterRef("occurrence__activity__transport_service__route_id")
        )
        .order_by("-position")
        .values("place_id")[:1]
    )
    return (
        upcoming_departures()
        .filter(
            occurrence__start_at__gte=start,
            occurrence__start_at__lt=end,
            occurrence__activity__transport_service__route__stops__position=1,
            occurrence__activity__transport_service__route__stops__place=origin,
        )
        .annotate(route_destination_id=Subquery(last_place))
        .filter(route_destination_id=destination.pk)
        .distinct()
    )


def departure_available_offers(departure):
    return [offer for offer in departure.occurrence.offers.all() if offer.is_currently_available]


def departure_capacity_snapshot(departure):
    pool = departure.passenger_capacity_pool
    active = (
        pool.reservations.filter(
            Q(status=CapacityReservationStatus.COMMITTED)
            | Q(status=CapacityReservationStatus.HELD, expires_at__gt=timezone.now())
            | Q(status=CapacityReservationStatus.HELD, expires_at__isnull=True)
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    remaining = None if pool.total_quantity is None else max(pool.total_quantity - active, 0)
    return {
        "total": pool.total_quantity,
        "consumed": active,
        "remaining": remaining,
        "sold_out": remaining == 0 if remaining is not None else False,
    }


def departure_manifest(departure):
    accesses = (
        Access.objects.filter(occurrence=departure.occurrence)
        .select_related("beneficiary")
        .prefetch_related("uses")
    )
    rows = []
    for access in accesses:
        accepted = next(
            (use for use in access.uses.all() if use.result == AccessUseResult.ACCEPTED),
            None,
        )
        rows.append(
            {
                "beneficiary": access.beneficiary,
                "access_status": access.status,
                "boarded": accepted is not None,
                "scanned_at": accepted.used_at if accepted else None,
            }
        )
    return rows
