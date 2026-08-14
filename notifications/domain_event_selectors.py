from django.contrib.auth import get_user_model

from access.models import AccessStatus
from journeys.models import JourneyStatus


User = get_user_model()


ACTIVE_OCCURRENCE_JOURNEY_STATUSES = {
    JourneyStatus.SUBMITTED,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.APPROVED,
    JourneyStatus.PENDING_PAYMENT,
    JourneyStatus.CONFIRMED,
    JourneyStatus.FULFILLED,
}


def occurrence_recipient_ids(occurrence):
    access_ids = occurrence.accesses.filter(
        beneficiary__isnull=False,
        status__in={AccessStatus.PENDING, AccessStatus.VALID, AccessStatus.USED},
    ).values_list("beneficiary_id", flat=True)
    journey_ids = occurrence.journeys.filter(
        beneficiary__isnull=False,
        status__in=ACTIVE_OCCURRENCE_JOURNEY_STATUSES,
    ).values_list("beneficiary_id", flat=True)
    return set(access_ids).union(journey_ids)


def occurrence_recipients(occurrence):
    ids = occurrence_recipient_ids(occurrence)
    return User.objects.filter(pk__in=ids, is_active=True).order_by("pk")
