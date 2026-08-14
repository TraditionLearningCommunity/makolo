from django.core.exceptions import ValidationError
from django.db import transaction

from .models import JourneyStatus
from .services import _locked, _transition_locked


@transaction.atomic
def sync_legacy_journey_status(*, journey, status, actor=None, reason="legacy_bridge"):
    if status not in JourneyStatus.values:
        raise ValidationError("État Journey legacy inconnu.")
    journey = _locked(journey)
    if journey.status == status:
        return journey
    return _transition_locked(
        journey,
        new_status=status,
        actor=actor,
        reason=reason,
    )
