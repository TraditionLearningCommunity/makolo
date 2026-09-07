from access.models import AccessStatus
from journeys.models import JourneyStatus


ACTIVE_PARTICIPATION_JOURNEY_STATUSES = {
    JourneyStatus.SUBMITTED,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.APPROVED,
    JourneyStatus.PENDING_PAYMENT,
    JourneyStatus.CONFIRMED,
    JourneyStatus.FULFILLED,
}

ACTIVE_PARTICIPATION_ACCESS_STATUSES = {
    AccessStatus.PENDING,
    AccessStatus.VALID,
    AccessStatus.USED,
}


def occurrence_participant_ids(occurrence):
    """Profiles with a current canonical Journey or Access relation to one Occurrence."""

    access_ids = occurrence.access_rights.filter(
        beneficiary__isnull=False,
        status__in=ACTIVE_PARTICIPATION_ACCESS_STATUSES,
    ).values_list("beneficiary_id", flat=True)
    journey_ids = occurrence.journeys.filter(
        beneficiary__isnull=False,
        status__in=ACTIVE_PARTICIPATION_JOURNEY_STATUSES,
    ).values_list("beneficiary_id", flat=True)
    return set(access_ids).union(journey_ids)


def activity_participant_ids(activity):
    """Profiles with a current canonical Journey or Access relation to an Activity."""

    access_ids = activity.access_rights.filter(
        beneficiary__isnull=False,
        status__in=ACTIVE_PARTICIPATION_ACCESS_STATUSES,
    ).values_list("beneficiary_id", flat=True)
    journey_ids = activity.journeys.filter(
        beneficiary__isnull=False,
        status__in=ACTIVE_PARTICIPATION_JOURNEY_STATUSES,
    ).values_list("beneficiary_id", flat=True)
    return set(access_ids).union(journey_ids)
