from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from access.services import issue_access
from activities.models import ActivityStatus, ActivityVisibility, OccurrenceStatus
from activities.services import cancel_occurrence, create_activity, create_occurrence, update_activity_common
from capacity.models import CapacityPool, CapacityReservationStatus
from commerce.models import OfferStatus, PaymentMode
from commerce.services import OrderSelection, confirm_order, create_offer, create_order
from journeys.models import Journey, WorkflowKind

from .models import TransportDeparture, TransportRoute, TransportRouteStop, TransportService, Vehicle


def _validate_route(route):
    if route.stops.count() < 2:
        raise ValidationError("Une Route Transport doit contenir au moins une origine et une destination.")


@transaction.atomic
def create_transport_route(*, space, name, stops, code="", active=True):
    if len(stops) < 2:
        raise ValidationError("Une Route Transport doit contenir au moins deux arrêts.")
    route = TransportRoute.objects.create(space=space, name=name.strip(), code=code.strip(), active=active)
    for position, raw in enumerate(stops, start=1):
        place = raw.get("place") if isinstance(raw, dict) else raw
        values = raw if isinstance(raw, dict) else {}
        TransportRouteStop.objects.create(route=route, place=place, position=position, boarding_allowed=values.get("boarding_allowed", True), alighting_allowed=values.get("alighting_allowed", True), notes=values.get("notes", ""))
    return route


@transaction.atomic
def create_transport_service(*, space, created_by, route, title=None, description="", mode="road"):
    _validate_route(route)
    if route.space_id != space.pk:
        raise ValidationError("La Route appartient à un autre Espace.")
    activity = create_activity(space=space, created_by=created_by, title=(title or route.name), description=description, visibility=ActivityVisibility.PUBLIC)
    service = TransportService(activity=activity, route=route, mode=mode)
    service.full_clean(); service.save()
    return service


@transaction.atomic
def create_transport_departure(*, service, start_at, timezone_name, end_at=None, vehicle=None, capacity=None, boarding_instructions="", operational_reference=""):
    if not service.route.active:
        raise ValidationError("Impossible de créer un départ sur une Route inactive.")
    if vehicle is not None:
        if not vehicle.active:
            raise ValidationError("Un véhicule inactif ne peut pas être affecté.")
        if vehicle.space_id != service.activity.space_id:
            raise ValidationError("Le véhicule appartient à un autre Espace.")
    total = capacity if capacity is not None else (vehicle.passenger_capacity if vehicle else None)
    if total is not None and vehicle and total > vehicle.passenger_capacity:
        raise ValidationError("La capacité vendable dépasse la capacité physique du véhicule.")
    occurrence = create_occurrence(activity=service.activity, start_at=start_at, end_at=end_at, timezone=timezone_name, status=OccurrenceStatus.DRAFT, label="Départ")
    pool = CapacityPool.objects.create(activity=service.activity, occurrence=occurrence, label="Voyageurs", total_quantity=total)
    departure = TransportDeparture(occurrence=occurrence, vehicle=vehicle, passenger_capacity_pool=pool, boarding_instructions=boarding_instructions, operational_reference=operational_reference)
    departure.full_clean(); departure.save()
    return departure


@transaction.atomic
def assign_vehicle(*, departure, vehicle):
    if not vehicle.active:
        raise ValidationError("Un véhicule inactif ne peut pas être affecté.")
    if vehicle.space_id != departure.occurrence.activity.space_id:
        raise ValidationError("Le véhicule appartient à un autre Espace.")
    consumed = departure.passenger_capacity_pool.reservations.filter(status__in=[CapacityReservationStatus.HELD, CapacityReservationStatus.COMMITTED]).aggregate(total=Sum("quantity"))["total"] or 0
    if consumed > vehicle.passenger_capacity:
        raise ValidationError("Ce véhicule est trop petit pour la capacité déjà consommée.")
    pool = departure.passenger_capacity_pool
    if pool.total_quantity is not None and pool.total_quantity > vehicle.passenger_capacity:
        if consumed > vehicle.passenger_capacity:
            raise ValidationError("Ce véhicule est trop petit pour les réservations existantes.")
        pool.total_quantity = vehicle.passenger_capacity
        pool.save(update_fields=["total_quantity", "updated_at"])
    departure.vehicle = vehicle
    departure.full_clean(); departure.save(update_fields=["vehicle", "updated_at"])
    return departure


@transaction.atomic
def configure_transport_fare(*, departure, name, unit_price, currency="USD", payment_mode=PaymentMode.UPFRONT):
    return create_offer(activity=departure.occurrence.activity, occurrence=departure.occurrence, capacity_pool=departure.passenger_capacity_pool, name=name, unit_price=unit_price, currency=currency, payment_mode=payment_mode, min_quantity=1, max_quantity=1, status=OfferStatus.ACTIVE)


@transaction.atomic
def publish_transport_departure(*, departure):
    _validate_route(departure.occurrence.activity.transport_service.route)
    if not departure.occurrence.activity.transport_service.route.active:
        raise ValidationError("La Route est inactive.")
    if not departure.occurrence.offers.filter(status=OfferStatus.ACTIVE).exists():
        raise ValidationError("Un départ publié doit proposer au moins un Tarif actif.")
    if departure.occurrence.activity.status != ActivityStatus.PUBLISHED:
        update_activity_common(activity=departure.occurrence.activity, status=ActivityStatus.PUBLISHED)
    occurrence = departure.occurrence
    occurrence.status = OccurrenceStatus.SCHEDULED
    occurrence.save(update_fields=["status", "updated_at"])
    return departure


def cancel_transport_departure(*, departure):
    cancel_occurrence(occurrence=departure.occurrence)
    return departure


@transaction.atomic
def book_transport(*, departure, offer, participant, idempotency_key=None):
    if offer.occurrence_id != departure.occurrence_id or offer.capacity_pool_id != departure.passenger_capacity_pool_id:
        raise ValidationError("Ce Tarif ne correspond pas au départ sélectionné.")
    if departure.occurrence.status != OccurrenceStatus.SCHEDULED or departure.occurrence.start_at <= timezone.now():
        raise ValidationError("Ce départ n’est pas réservable.")
    journey = Journey.objects.create(initiated_by=participant, beneficiary=participant, activity=departure.occurrence.activity, occurrence=departure.occurrence, workflow=WorkflowKind.PURCHASE if offer.payment_mode == PaymentMode.UPFRONT else WorkflowKind.RESERVATION)
    order = create_order(journey=journey, buyer=participant, selections=[OrderSelection(offer=offer, quantity=1, beneficiary=participant)], idempotency_key=idempotency_key, expires_at=timezone.now() + timedelta(minutes=15) if offer.payment_mode == PaymentMode.UPFRONT else None)
    access = None
    if offer.payment_mode in {PaymentMode.NONE, PaymentMode.ON_SITE}:
        order = confirm_order(order=order, actor=participant)
        journey.refresh_from_db()
        access = issue_access(beneficiary=participant, activity=journey.activity, occurrence=journey.occurrence, journey=journey, source_key="transport-ticket")
    return {"journey": journey, "order": order, "access": access}
