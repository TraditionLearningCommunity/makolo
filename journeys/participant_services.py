from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import JourneyStatus, WorkflowKind
from .services import _locked, _transition_locked


def _ensure_invitation_beneficiary(actor, journey):
    if not getattr(actor, "is_authenticated", False) or journey.beneficiary_id != getattr(actor, "pk", None):
        raise PermissionDenied("Cette invitation appartient à une autre personne.")
    if journey.workflow != WorkflowKind.INVITATION:
        raise ValidationError("Cette démarche n’est pas une invitation.")


@transaction.atomic
def accept_invitation(*, journey, actor):
    """Accept an invitation as its beneficiary using canonical Journey transitions."""
    journey = _locked(journey)
    _ensure_invitation_beneficiary(actor, journey)
    if journey.status == JourneyStatus.CONFIRMED:
        return journey
    if journey.status != JourneyStatus.SUBMITTED:
        raise ValidationError("Cette invitation ne peut plus être acceptée.")
    journey = _transition_locked(
        journey,
        new_status=JourneyStatus.APPROVED,
        actor=actor,
        reason="beneficiary_accepted_invitation",
    )
    return _transition_locked(
        journey,
        new_status=JourneyStatus.CONFIRMED,
        actor=actor,
        reason="invitation_confirmed",
    )


@transaction.atomic
def decline_invitation(*, journey, actor):
    """Decline an invitation as its beneficiary without exposing internal approval APIs."""
    journey = _locked(journey)
    _ensure_invitation_beneficiary(actor, journey)
    if journey.status == JourneyStatus.CANCELLED:
        return journey
    if journey.status != JourneyStatus.SUBMITTED:
        raise ValidationError("Cette invitation ne peut plus être refusée.")
    return _transition_locked(
        journey,
        new_status=JourneyStatus.CANCELLED,
        actor=actor,
        reason="beneficiary_declined_invitation",
    )
