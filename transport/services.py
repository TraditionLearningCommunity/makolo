from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from access.services import issue_access
from activities.models import ActivityStatus, ActivityVisibility, OccurrenceStatus
from activities.services import (
    cancel_occurrence,
    create_activity,
    create_occurrence,
    reschedule_occurrence,
    set_occurrence_status,
    update_activity_common,
)
from capacity.models import CapacityPool, CapacityReservationStatus
from commerce.models import CommerceOrderStatus, OfferStatus, PaymentMode
from commerce.services import OrderSelection, confirm_order, create_offer, create_order
from journeys.models import WorkflowKind
from journeys.services import create_journey, submit_journey

from .models import TransportDeparture, TransportRoute, TransportRouteStop, TransportService, Vehicle


def _validate_route(route):
    if route.stops.count() < 2:
        raise ValidationError("Une Route Transport doit contenir au moins une origine et une destination.")


def _validate_space_object(*, space, obj, label):
    if getattr(obj, "space_id", None) != space.pk:
        raise ValidationError(f"{label} appartient à un autre Espace.")


@transaction.atomic
def create_transport_route(*, space, name, stops, code="", active=True):
    if len(stops) < 2:
        raise ValidationError("Une Route Transport doit contenir au moins deux arrêts.")
    route = TransportRoute.objects.create(
        space=space,
        name=name.strip(),
        code=code.strip(),
        active=active,
    )
    for position, raw in enumerate(stops, start=1):
        place = raw.get("place") if isinstance(raw, dict) else raw
        values = raw if isinstance(raw, dict) else {}
        TransportRouteStop.objects.create(
            route=route,
            place=place,
            position=position,
            boarding_allowed=values.get("boarding_allowed", True),
            alighting_allowed=values.get("alighting_allowed", True),
            notes=values.get("notes", ""),
        )
    _validate_route(route)
    return route


@transaction.atomic
def create_transport_service(*, space, created_by, route, title=None, description="", mode="road"):
    _validate_route(route)
    _validate_space_object(space=space, obj=route, label="La Route")
    activity = create_activity(
        space=space,
        created_by=created_by,
        title=(title or route.name),
        description=description,
        visibility=ActivityVisibility.PUBLIC,
    )
    service = TransportService(activity=activity, route=route, mode=mode)
    service.full_clean()
    service.save()
    return service


@transaction.atomic
def create_transport_vehicle(
    *,
    space,
    label,
    passenger_capacity,
    registration="",
    vehicle_type="bus",
    active=True,
):
    vehicle = Vehicle(
        space=space,
        label=label.strip(),
        registration=registration.strip(),
        vehicle_type=vehicle_type,
        passenger_capacity=passenger_capacity,
        active=active,
    )
    vehicle.full_clean()
    vehicle.save()
    return vehicle


@transaction.atomic
def create_transport_departure(
    *,
    service,
    start_at,
    timezone_name,
    end_at=None,
    vehicle=None,
    capacity=None,
    boarding_instructions="",
    operational_reference="",
):
    _validate_route(service.route)
    if not service.route.active:
        raise ValidationError("Impossible de créer un départ sur une Route inactive.")
    if vehicle is not None:
        if not vehicle.active:
            raise ValidationError("Un véhicule inactif ne peut pas être affecté.")
        if vehicle.space_id != service.activity.space_id:
            raise ValidationError("Le véhicule appartient à un autre Espace.")
    total = capacity if capacity is not None else (vehicle.passenger_capacity if vehicle else None)
    if total is not None and total <= 0:
        raise ValidationError("La capacité passagers doit être strictement positive.")
    if total is not None and vehicle and total > vehicle.passenger_capacity:
        raise ValidationError("La capacité vendable dépasse la capacité physique du véhicule.")
    occurrence = create_occurrence(
        activity=service.activity,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_name,
        status=OccurrenceStatus.DRAFT,
        label="Départ",
    )
    pool = CapacityPool.objects.create(
        activity=service.activity,
        occurrence=occurrence,
        label="Voyageurs",
        total_quantity=total,
    )
    departure = TransportDeparture(
        occurrence=occurrence,
        vehicle=vehicle,
        passenger_capacity_pool=pool,
        boarding_instructions=boarding_instructions,
        operational_reference=operational_reference,
    )
    departure.full_clean()
    departure.save()
    return departure


@transaction.atomic
def assign_vehicle(*, departure, vehicle):
    if not vehicle.active:
        raise ValidationError("Un véhicule inactif ne peut pas être affecté.")
    if vehicle.space_id != departure.occurrence.activity.space_id:
        raise ValidationError("Le véhicule appartient à un autre Espace.")
    consumed = (
        departure.passenger_capacity_pool.reservations.filter(
            Q(status=CapacityReservationStatus.COMMITTED)
            | Q(status=CapacityReservationStatus.HELD, expires_at__isnull=True)
            | Q(status=CapacityReservationStatus.HELD, expires_at__gt=timezone.now())
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    if consumed > vehicle.passenger_capacity:
        raise ValidationError("Ce véhicule est trop petit pour la capacité déjà consommée.")
    pool = departure.passenger_capacity_pool
    if pool.total_quantity is not None and pool.total_quantity > vehicle.passenger_capacity:
        pool.total_quantity = vehicle.passenger_capacity
        pool.full_clean()
        pool.save(update_fields=["total_quantity", "updated_at"])
    departure.vehicle = vehicle
    departure.full_clean()
    departure.save(update_fields=["vehicle", "updated_at"])
    return departure


@transaction.atomic
def configure_transport_fare(
    *,
    departure,
    name,
    unit_price,
    currency="USD",
    payment_mode=PaymentMode.UPFRONT,
):
    if payment_mode not in {PaymentMode.UPFRONT, PaymentMode.ON_SITE, PaymentMode.NONE}:
        raise ValidationError("Ce mode de paiement n’est pas activé pour Transport.")
    return create_offer(
        activity=departure.occurrence.activity,
        occurrence=departure.occurrence,
        capacity_pool=departure.passenger_capacity_pool,
        name=name,
        unit_price=unit_price,
        currency=currency,
        payment_mode=payment_mode,
        min_quantity=1,
        max_quantity=1,
        status=OfferStatus.ACTIVE,
    )


@transaction.atomic
def publish_transport_departure(*, departure):
    route = departure.occurrence.activity.transport_service.route
    _validate_route(route)
    if not route.active:
        raise ValidationError("La Route est inactive.")
    if not departure.occurrence.offers.filter(status=OfferStatus.ACTIVE).exists():
        raise ValidationError("Un départ publié doit proposer au moins un Tarif actif.")
    if departure.occurrence.activity.status != ActivityStatus.PUBLISHED:
        update_activity_common(activity=departure.occurrence.activity, status=ActivityStatus.PUBLISHED)
    set_occurrence_status(occurrence=departure.occurrence, status=OccurrenceStatus.SCHEDULED)
    departure.occurrence.refresh_from_db()
    return departure


@transaction.atomic
def reschedule_transport_departure(*, departure, start_at, end_at=None, timezone_name=None):
    reschedule_occurrence(
        occurrence=departure.occurrence,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_name,
    )
    departure.occurrence.refresh_from_db()
    return departure


def cancel_transport_departure(*, departure):
    cancel_occurrence(occurrence=departure.occurrence)
    departure.occurrence.refresh_from_db()
    return departure


def issue_transport_ticket_for_order(*, order, issued_by=None):
    order = order.__class__.objects.select_related(
        "journey__activity",
        "journey__occurrence",
        "journey__beneficiary",
    ).get(pk=order.pk)
    if order.status != CommerceOrderStatus.CONFIRMED:
        raise ValidationError("Le billet ne peut être émis qu’après confirmation de la commande.")
    journey = order.journey
    try:
        journey.activity.transport_service
    except Exception as exc:
        raise ValidationError("Cette commande n’appartient pas à un Trajet Transport.") from exc
    if journey.occurrence_id is None:
        raise ValidationError("Un billet Transport doit cibler un Départ.")
    return issue_access(
        beneficiary=journey.beneficiary,
        activity=journey.activity,
        occurrence=journey.occurrence,
        journey=journey,
        issued_by=issued_by,
        single_use=True,
        source_key="transport-ticket",
    )


@transaction.atomic
def book_transport(*, departure, offer, participant, idempotency_key=None):
    if not getattr(participant, "is_authenticated", False):
        raise ValidationError("Une authentification est requise pour réserver un voyage.")
    if offer.occurrence_id != departure.occurrence_id or offer.capacity_pool_id != departure.passenger_capacity_pool_id:
        raise ValidationError("Ce Tarif ne correspond pas au départ sélectionné.")
    if departure.occurrence.status != OccurrenceStatus.SCHEDULED or departure.occurrence.start_at <= timezone.now():
        raise ValidationError("Ce départ n’est pas réservable.")
    if not departure.occurrence.activity.transport_service.route.active:
        raise ValidationError("Ce Trajet n’est plus réservable.")

    workflow = WorkflowKind.PURCHASE if offer.payment_mode == PaymentMode.UPFRONT else WorkflowKind.RESERVATION
    journey = create_journey(
        initiated_by=participant,
        beneficiary=participant,
        activity=departure.occurrence.activity,
        occurrence=departure.occurrence,
        workflow=workflow,
    )
    if workflow == WorkflowKind.RESERVATION:
        journey = submit_journey(journey=journey, actor=participant, reason="transport_reservation")

    order = create_order(
        journey=journey,
        buyer=participant,
        payee_space=departure.occurrence.activity.space,
        selections=[OrderSelection(offer=offer, quantity=1, beneficiary=participant)],
        idempotency_key=idempotency_key,
        expires_at=timezone.now() + timedelta(minutes=15) if offer.payment_mode == PaymentMode.UPFRONT else None,
    )
    access = None
    if offer.payment_mode in {PaymentMode.NONE, PaymentMode.ON_SITE}:
        order = confirm_order(order=order, actor=participant)
        access = issue_transport_ticket_for_order(order=order, issued_by=participant)
    return {"journey": order.journey, "order": order, "access": access}
