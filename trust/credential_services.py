from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from access.models import AccessUseResult
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import JourneyStatus

from .credential_models import Credential, CredentialStatus, CredentialType


def _authenticated(actor) -> bool:
    return bool(actor and getattr(actor, "is_authenticated", False))


def can_issue_credential(*, actor, activity) -> bool:
    """Resolve issuance authority from current Mandates on every call."""
    if not _authenticated(actor):
        return False
    if can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        return True
    return bool(
        activity.space_id
        and can(actor, PermissionCode.SPACE_TRUST_MANAGE, space=activity.space)
    )


def _require_issue_authority(*, actor, activity) -> None:
    if not can_issue_credential(actor=actor, activity=activity):
        raise PermissionDenied("Un Mandate autorisant la gestion de cette Activity ou de son Trust est requis.")


def _issuer_for_activity(activity):
    if activity.space_id:
        return activity.space, None
    if activity.owner_profile_id:
        return None, activity.owner_profile
    raise ValidationError(
        "Cette Activity historique ne possède pas d’opérateur logique permettant une émission sûre."
    )


def _credential_eligible(*, journey, credential_type) -> bool:
    if credential_type == CredentialType.COMPLETION:
        return bool(journey and journey.status == JourneyStatus.FULFILLED)
    if credential_type == CredentialType.PARTICIPATION:
        return bool(
            journey
            and journey.accesses.filter(uses__result=AccessUseResult.ACCEPTED).exists()
        )
    if credential_type == CredentialType.ATTESTATION:
        # Generic attestations are deliberate organizer decisions. They are not
        # automatically inferred from Access or another convenience signal.
        return True
    return False


@transaction.atomic
def issue_credential(
    *,
    activity,
    subject_profile,
    credential_type,
    actor,
    journey=None,
    occurrence=None,
    title="",
    statement="",
) -> Credential:
    _require_issue_authority(actor=actor, activity=activity)
    if credential_type not in CredentialType.values:
        raise ValidationError({"credential_type": "Type de Credential non pris en charge."})
    if subject_profile is None:
        raise ValidationError({"subject_profile": "Un bénéficiaire Profile est requis."})
    if journey is not None and journey.activity_id != activity.pk:
        raise ValidationError({"journey": "La Journey doit concerner l’Activity source."})
    if journey is not None and journey.beneficiary_id != subject_profile.pk:
        raise ValidationError({"subject_profile": "Le Credential doit viser le bénéficiaire Profile de la Journey."})
    if occurrence is None and journey is not None:
        occurrence = journey.occurrence
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L’Occurrence doit appartenir à l’Activity source."})
    if not _credential_eligible(journey=journey, credential_type=credential_type):
        raise ValidationError("Le fait canonique requis pour délivrer ce Credential n’est pas établi.")

    issuer_space, issuer_profile = _issuer_for_activity(activity)
    title = (title or "").strip() or f"{dict(CredentialType.choices)[credential_type]} — {activity.title}"
    statement = (statement or "").strip()

    existing = Credential.objects.select_for_update().filter(
        subject_profile=subject_profile,
        issuer_space=issuer_space,
        issuer_profile=issuer_profile,
        activity=activity,
        occurrence=occurrence,
        journey=journey,
        credential_type=credential_type,
        title=title,
        statement=statement,
        status=CredentialStatus.ISSUED,
    ).order_by().first()
    if existing:
        return existing

    credential = Credential(
        subject_profile=subject_profile,
        issuer_space=issuer_space,
        issuer_profile=issuer_profile,
        issued_by=actor,
        activity=activity,
        occurrence=occurrence,
        journey=journey,
        credential_type=credential_type,
        title=title,
        statement=statement,
    )
    credential.full_clean()
    credential.save()
    return credential


@transaction.atomic
def revoke_credential(*, credential, actor, reason="") -> Credential:
    locked = (
        Credential.objects.select_for_update()
        .select_related("activity__space", "activity__owner_profile")
        .get(pk=credential.pk)
    )
    allowed = can_issue_credential(actor=actor, activity=locked.activity)
    allowed = allowed or (
        _authenticated(actor) and can(actor, PermissionCode.PLATFORM_TRUST_REVIEW)
    )
    if not allowed:
        raise PermissionDenied("Autorité de révocation du Credential requise.")
    if locked.status == CredentialStatus.REVOKED:
        return locked

    locked.status = CredentialStatus.REVOKED
    locked.revoked_by = actor
    locked.revoked_at = timezone.now()
    locked.revoke_reason = (reason or "").strip()
    locked._allow_status_transition = True
    locked.save(
        update_fields=[
            "status",
            "revoked_by",
            "revoked_at",
            "revoke_reason",
            "updated_at",
        ]
    )
    return locked
