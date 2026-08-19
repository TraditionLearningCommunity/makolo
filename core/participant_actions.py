from django.db import transaction

from access.services import issue_access
from journeys.participant_services import accept_invitation, decline_invitation


@transaction.atomic
def participant_accept_invitation(*, journey, actor):
    journey = accept_invitation(journey=journey, actor=actor)
    access = issue_access(
        beneficiary=journey.beneficiary,
        activity=journey.activity,
        occurrence=journey.occurrence,
        journey=journey,
        source_key="participant-invitation",
        create_credential=True,
    )
    return journey, access


@transaction.atomic
def participant_decline_invitation(*, journey, actor):
    return decline_invitation(journey=journey, actor=actor)
