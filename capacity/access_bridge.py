from django.core.exceptions import ValidationError
from django.db import transaction

from access.services import issue_access

from .models import CapacityReservation, CapacityReservationStatus
from .services import commit_capacity


@transaction.atomic
def issue_access_from_capacity(
    *,
    reservation,
    beneficiary,
    source_key,
    issued_by=None,
    status="valid",
    valid_from=None,
    valid_until=None,
    single_use=True,
    create_credential=True,
):
    reservation = (
        CapacityReservation.objects.select_for_update(of=("self",))
        .select_related("pool", "pool__activity", "pool__occurrence", "journey")
        .order_by()
        .get(pk=reservation.pk)
    )
    if reservation.status == CapacityReservationStatus.HELD:
        reservation = commit_capacity(reservation=reservation)
    if reservation.status != CapacityReservationStatus.COMMITTED:
        raise ValidationError("Un Accès capacitaire exige une réservation committed.")
    if reservation.journey.activity_id != reservation.pool.activity_id:
        raise ValidationError("La réservation Capacity est incohérente avec sa Démarche.")

    return issue_access(
        beneficiary=beneficiary,
        activity=reservation.pool.activity,
        occurrence=reservation.pool.occurrence,
        journey=reservation.journey,
        issued_by=issued_by,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        single_use=single_use,
        source_key=source_key,
        create_credential=create_credential,
    )
