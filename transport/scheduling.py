from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from activities.models import OccurrencePlaceRole, OccurrenceStatus, OccurrenceTimingKind
from activities.services import (
    attach_occurrence_place,
    create_occurrence_schedule,
    materialize_occurrence_schedule,
)
from capacity.models import CapacityPool

from .models import TransportDeparture
from .services import configure_transport_fare


@transaction.atomic
def create_transport_departure_schedule(
    *,
    service,
    created_by,
    frequency,
    starts_on,
    ends_on,
    materialize_through,
    timezone_name,
    start_time,
    interval=1,
    duration_minutes=None,
    weekdays=(),
    month_day=None,
    month=None,
    vehicle=None,
    capacity=None,
    fares=(),
    boarding_instructions="",
    operational_reference_prefix="",
):
    """Create one recurring Transport slot and materialize concrete departures.

    Vehicle, Capacity and Offer remain owned by their canonical domains. They are
    copied only onto the concrete Occurrences materialized in this bounded call;
    the generic OccurrenceSchedule does not become a second source of truth.
    """
    if start_time is None:
        raise ValidationError("Un planning de départ Transport exige une heure exacte.")
    if ends_on is None:
        raise ValidationError(
            "Le planning Transport doit être borné tant que les defaults véhicule/capacité/tarif ne sont pas persistés par leurs domaines propriétaires."
        )
    if materialize_through > ends_on:
        materialize_through = ends_on
    if vehicle is not None:
        if not vehicle.active:
            raise ValidationError("Un véhicule inactif ne peut pas être affecté.")
        if vehicle.space_id != service.activity.space_id:
            raise ValidationError("Le véhicule appartient à un autre Espace.")
    total = capacity if capacity is not None else (vehicle.passenger_capacity if vehicle else None)
    if total is not None and total <= 0:
        raise ValidationError("La capacité passagers doit être strictement positive.")
    if total is not None and vehicle is not None and total > vehicle.passenger_capacity:
        raise ValidationError("La capacité vendable dépasse la capacité physique du véhicule.")

    schedule = create_occurrence_schedule(
        activity=service.activity,
        created_by=created_by,
        frequency=frequency,
        starts_on=starts_on,
        ends_on=ends_on,
        timezone=timezone_name,
        interval=interval,
        timing_kind=OccurrenceTimingKind.EXACT,
        start_time=start_time,
        duration_minutes=duration_minutes,
        weekdays=weekdays,
        month_day=month_day,
        month=month,
        label="Départ",
        occurrence_status=OccurrenceStatus.DRAFT,
    )
    departures = materialize_transport_departure_schedule(
        schedule=schedule,
        service=service,
        materialize_through=materialize_through,
        vehicle=vehicle,
        capacity=total,
        fares=fares,
        boarding_instructions=boarding_instructions,
        operational_reference_prefix=operational_reference_prefix,
    )
    return schedule, departures


@transaction.atomic
def materialize_transport_departure_schedule(
    *,
    schedule,
    service,
    materialize_through,
    vehicle=None,
    capacity=None,
    fares=(),
    boarding_instructions="",
    operational_reference_prefix="",
):
    if schedule.activity_id != service.activity_id:
        raise ValidationError("Ce planning n’appartient pas au service Transport.")
    occurrences = materialize_occurrence_schedule(schedule=schedule, through_date=materialize_through)
    # Include previously materialized slots missing their vertical projection so
    # a retry after a partial failure can repair the same bounded window.
    pending = list(
        schedule.generated_occurrences.filter(
            start_date__lte=materialize_through,
            transport_departure__isnull=True,
        ).order_by("start_date", "start_time", "id")
    )
    by_id = {row.pk: row for row in [*occurrences, *pending]}
    departures = []
    origin = service.route.origin
    for occurrence in sorted(by_id.values(), key=lambda row: (row.start_date, row.start_time, str(row.pk))):
        if occurrence.start_at is None:
            raise ValidationError("Un départ Transport matérialisé doit posséder un instant exact.")
        if origin is not None:
            attach_occurrence_place(
                occurrence=occurrence,
                place=origin,
                role=OccurrencePlaceRole.PRIMARY,
                position=0,
            )
        pool = CapacityPool.objects.create(
            activity=service.activity,
            occurrence=occurrence,
            label="Voyageurs",
            total_quantity=capacity,
            source_key=f"transport-schedule:{schedule.pk}:{occurrence.pk}:capacity",
        )
        reference = f"{operational_reference_prefix}{occurrence.start_date.isoformat()}"
        departure = TransportDeparture(
            occurrence=occurrence,
            vehicle=vehicle,
            passenger_capacity_pool=pool,
            boarding_instructions=boarding_instructions,
            operational_reference=reference[:80],
        )
        departure.full_clean()
        departure.save()
        for fare in fares:
            configure_transport_fare(departure=departure, **dict(fare))
        departures.append(departure)
    return departures
