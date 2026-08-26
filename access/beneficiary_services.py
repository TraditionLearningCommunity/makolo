from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from domain_events.contracts import DomainEventType

from .models import Access, AccessStatus, CredentialStatus
from .services import _UNSET, _create_credential, _emit_access_event, issue_access


@transaction.atomic
def issue_access_for_holder(
    *,
    activity,
    beneficiary=None,
    external_beneficiary=None,
    occurrence=None,
    journey=None,
    issued_by=None,
    status=AccessStatus.VALID,
    valid_from=_UNSET,
    valid_until=_UNSET,
    single_use=True,
    source_key="",
    create_credential=True,
    audit_reason="",
):
    """Issue one individual Access to either a Makolo Profile or an external holder."""
    if bool(beneficiary) == bool(external_beneficiary):
        raise ValidationError("Un Accès doit cibler exactement un bénéficiaire Profile ou externe.")
    if beneficiary is not None:
        return issue_access(
            beneficiary=beneficiary,
            activity=activity,
            occurrence=occurrence,
            journey=journey,
            issued_by=issued_by,
            status=status,
            valid_from=valid_from,
            valid_until=valid_until,
            single_use=single_use,
            source_key=source_key,
            create_credential=create_credential,
            audit_reason=audit_reason,
        )

    if journey is not None:
        from journeys.models import Journey

        journey = (
            Journey.objects.select_for_update(of=("self",))
            .select_related("activity", "occurrence", "external_beneficiary")
            .order_by()
            .get(pk=journey.pk)
        )
        if journey.activity_id != activity.pk:
            raise ValidationError("La Démarche appartient à une autre Activity.")
        if journey.external_beneficiary_id != external_beneficiary.pk:
            raise ValidationError("Le bénéficiaire externe doit correspondre à celui de la Démarche.")
        if occurrence is not None and journey.occurrence_id and journey.occurrence_id != occurrence.pk:
            raise ValidationError("L’Occurrence est incohérente avec la Démarche.")
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError("L’Occurrence appartient à une autre Activity.")

    source_key = (source_key or "").strip()[:180]
    if journey is not None and not source_key:
        source_key = "primary"
    if journey is not None and source_key:
        existing = (
            Access.objects.select_for_update(of=("self",))
            .filter(journey=journey, source_key=source_key)
            .order_by()
            .first()
        )
        if existing:
            if (
                existing.external_beneficiary_id != external_beneficiary.pk
                or existing.beneficiary_id is not None
                or existing.activity_id != activity.pk
                or existing.occurrence_id != getattr(occurrence, "pk", None)
            ):
                raise ValidationError("La clé d’émission existe déjà pour un autre résultat métier.")
            if create_credential and not existing.credentials.filter(status=CredentialStatus.ACTIVE).exists():
                _create_credential(existing)
            return existing

    if occurrence is not None:
        if valid_from is _UNSET:
            valid_from = occurrence.start_at
        if valid_until is _UNSET:
            valid_until = occurrence.end_at
    if valid_from is _UNSET:
        valid_from = None
    if valid_until is _UNSET:
        valid_until = None
    if valid_from and valid_until and valid_until <= valid_from:
        raise ValidationError("La fin de validité doit être postérieure au début.")
    if valid_until and valid_until <= timezone.now() and status == AccessStatus.VALID:
        status = AccessStatus.EXPIRED

    access = Access(
        beneficiary=None,
        external_beneficiary=external_beneficiary,
        activity=activity,
        occurrence=occurrence,
        journey=journey,
        issued_by=issued_by if getattr(issued_by, "is_authenticated", False) else None,
        status=status,
        single_use=single_use,
        source_key=source_key,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    try:
        access.save()
    except IntegrityError:
        if journey is not None and source_key:
            return Access.objects.get(journey=journey, source_key=source_key)
        raise
    if create_credential and access.status in {AccessStatus.PENDING, AccessStatus.VALID}:
        _create_credential(access)
    _emit_access_event(access, event_type=DomainEventType.ACCESS_ISSUED, audit_reason=audit_reason)
    return access
