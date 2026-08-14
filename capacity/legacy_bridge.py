from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CapacityReservation, CapacityReservationStatus
from .services import _set_status


@transaction.atomic
def sync_legacy_reservation_status(*, reservation, status, expires_at=None):
    if status not in CapacityReservationStatus.values:
        raise ValidationError("État Capacity legacy inconnu.")
    reservation = CapacityReservation.objects.select_for_update(of=("self",)).order_by().get(pk=reservation.pk)
    if reservation.status == status:
        if expires_at is not None and reservation.status == CapacityReservationStatus.HELD:
            reservation.expires_at = expires_at
            reservation.save(update_fields=["expires_at", "updated_at"])
        return reservation
    now = timezone.now()
    if status == CapacityReservationStatus.HELD:
        if reservation.status in {CapacityReservationStatus.RELEASED, CapacityReservationStatus.EXPIRED}:
            raise ValidationError("Une réservation legacy libérée/expirée ne peut pas redevenir held.")
        reservation.expires_at = expires_at
        return reservation
    return _set_status(reservation, status, now=now)
