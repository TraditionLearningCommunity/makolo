from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import CapacityPool, CapacityReservation, CapacityReservationStatus


class InsufficientCapacity(ValidationError):
    pass


def _validate_scope(pool, journey):
    if pool.activity_id != journey.activity_id:
        raise ValidationError("La Démarche appartient à une autre Activity que le pool de capacité.")
    if pool.occurrence_id and journey.occurrence_id != pool.occurrence_id:
        raise ValidationError("La Démarche doit cibler l’Occurrence du pool de capacité.")


def _consumed_quantity(pool, *, now):
    values = CapacityReservation.objects.filter(pool=pool).aggregate(
        held=Sum(
            "quantity",
            filter=Q(status=CapacityReservationStatus.HELD)
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
        ),
        committed=Sum("quantity", filter=Q(status=CapacityReservationStatus.COMMITTED)),
    )
    return (values["held"] or 0) + (values["committed"] or 0)


def _set_status(reservation, status, *, now=None):
    now = now or timezone.now()
    reservation.status = status
    if status == CapacityReservationStatus.COMMITTED and reservation.committed_at is None:
        reservation.committed_at = now
        reservation.expires_at = None
    elif status == CapacityReservationStatus.RELEASED and reservation.released_at is None:
        reservation.released_at = now
    elif status == CapacityReservationStatus.EXPIRED and reservation.expired_at is None:
        reservation.expired_at = now
    reservation._allow_status_transition = True
    reservation.save()
    return reservation


@transaction.atomic
def reserve_capacity(*, pool, journey, quantity=1, expires_at=None, source_key=""):
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValidationError("La quantité réservée doit être un entier strictement positif.") from exc
    if quantity <= 0:
        raise ValidationError("La quantité réservée doit être strictement positive.")

    pool = CapacityPool.objects.select_for_update(of=("self",)).order_by().get(pk=pool.pk)
    if not pool.is_active:
        raise ValidationError("Ce pool de capacité est inactif.")
    _validate_scope(pool, journey)
    source_key = (source_key or "").strip()[:180]
    if source_key:
        existing = CapacityReservation.objects.filter(
            pool=pool,
            journey=journey,
            source_key=source_key,
        ).order_by().first()
        if existing:
            if existing.quantity != quantity:
                raise ValidationError("Cette clé de réservation existe avec une autre quantité.")
            return existing

    now = timezone.now()
    if expires_at and expires_at <= now:
        raise ValidationError("L’expiration du hold doit être future.")
    if pool.total_quantity is not None:
        consumed = _consumed_quantity(pool, now=now)
        if consumed + quantity > pool.total_quantity:
            raise InsufficientCapacity("Capacité insuffisante.", code="insufficient_capacity")

    reservation = CapacityReservation(
        pool=pool,
        journey=journey,
        quantity=quantity,
        status=CapacityReservationStatus.HELD,
        expires_at=expires_at,
        source_key=source_key,
    )
    reservation.full_clean()
    try:
        reservation.save()
    except IntegrityError as exc:
        if source_key:
            existing = CapacityReservation.objects.filter(
                pool=pool,
                journey=journey,
                source_key=source_key,
            ).first()
            if existing:
                return existing
        raise ValidationError("Impossible de créer cette réservation de capacité de façon unique.") from exc
    return reservation


@transaction.atomic
def commit_capacity(*, reservation, now=None):
    now = now or timezone.now()
    reservation = CapacityReservation.objects.select_for_update(of=("self",)).order_by().get(pk=reservation.pk)
    if reservation.status == CapacityReservationStatus.COMMITTED:
        return reservation
    if reservation.status in {CapacityReservationStatus.RELEASED, CapacityReservationStatus.EXPIRED}:
        raise ValidationError("Cette réservation de capacité n’est plus engageable.")
    if reservation.expires_at and reservation.expires_at <= now:
        _set_status(reservation, CapacityReservationStatus.EXPIRED, now=now)
        raise ValidationError("Le hold de capacité a expiré.")
    return _set_status(reservation, CapacityReservationStatus.COMMITTED, now=now)


@transaction.atomic
def release_capacity(*, reservation, allow_committed=False, now=None):
    now = now or timezone.now()
    reservation = CapacityReservation.objects.select_for_update(of=("self",)).order_by().get(pk=reservation.pk)
    if reservation.status in {CapacityReservationStatus.RELEASED, CapacityReservationStatus.EXPIRED}:
        return reservation
    if reservation.status == CapacityReservationStatus.COMMITTED and not allow_committed:
        raise ValidationError("La libération d’une capacité engagée doit être explicitement autorisée par la politique métier.")
    return _set_status(reservation, CapacityReservationStatus.RELEASED, now=now)


@transaction.atomic
def expire_capacity(*, reservation, now=None):
    now = now or timezone.now()
    reservation = CapacityReservation.objects.select_for_update(of=("self",)).order_by().get(pk=reservation.pk)
    if reservation.status != CapacityReservationStatus.HELD:
        return reservation
    if reservation.expires_at is None or reservation.expires_at > now:
        return reservation
    return _set_status(reservation, CapacityReservationStatus.EXPIRED, now=now)


def expire_stale_capacity_reservations(*, now=None):
    now = now or timezone.now()
    reservation_ids = list(
        CapacityReservation.objects.filter(
            status=CapacityReservationStatus.HELD,
            expires_at__isnull=False,
            expires_at__lte=now,
        ).values_list("pk", flat=True)
    )
    changed = 0
    for reservation_id in reservation_ids:
        before = CapacityReservation.objects.only("status").get(pk=reservation_id).status
        reservation = expire_capacity(
            reservation=CapacityReservation(pk=reservation_id),
            now=now,
        )
        changed += int(before != reservation.status)
    return changed
