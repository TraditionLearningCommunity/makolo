from django.core.exceptions import ValidationError

from .models import ExternalBeneficiary, Journey, JourneyStatus


def create_external_beneficiary(*, created_by, display_name, email="", phone=""):
    if not getattr(created_by, "is_authenticated", False):
        raise ValidationError("Un Profile authentifié doit créer le bénéficiaire externe.")
    beneficiary = ExternalBeneficiary(
        display_name=display_name,
        email=email,
        phone=phone,
        created_by=created_by,
    )
    beneficiary.save()
    return beneficiary


def create_journey_for_holder(
    *,
    initiated_by,
    activity,
    workflow,
    beneficiary=None,
    external_beneficiary=None,
    occurrence=None,
    expires_at=None,
    status=JourneyStatus.DRAFT,
):
    """Create one Journey for exactly one logical beneficiary.

    Existing Profile flows continue through the established service. External
    holders use the same Journey model and transition machinery without a fake
    User. No email matching is performed here.
    """
    if bool(beneficiary) == bool(external_beneficiary):
        raise ValidationError("Choisissez exactement un bénéficiaire Profile ou externe.")
    if beneficiary is not None:
        from .services import create_journey

        return create_journey(
            initiated_by=initiated_by,
            beneficiary=beneficiary,
            activity=activity,
            occurrence=occurrence,
            workflow=workflow,
            expires_at=expires_at,
            status=status,
        )

    from .services import _check_occurrence, _emit_journey_event

    _check_occurrence(activity, occurrence)
    journey = Journey(
        initiated_by=initiated_by,
        beneficiary=None,
        external_beneficiary=external_beneficiary,
        activity=activity,
        occurrence=occurrence,
        workflow=workflow,
        status=status,
        expires_at=expires_at,
    )
    journey.save()
    if status != JourneyStatus.DRAFT:
        _emit_journey_event(journey, previous_status="", status=status)
    return journey
