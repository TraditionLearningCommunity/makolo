from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.signing import BadSignature, Signer
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import (
    Access,
    AccessCredential,
    AccessStatus,
    AccessUse,
    AccessUseResult,
    CredentialStatus,
    CredentialType,
    TERMINAL_ACCESS_STATUSES,
)


ACCESS_CREDENTIAL_SIGNING_SALT = "makolo.access.credential.v1"
_UNSET = object()


@dataclass(frozen=True)
class AccessValidationOutcome:
    result: str
    message: str
    access: Access | None = None
    credential: AccessCredential | None = None
    use: AccessUse | None = None

    @property
    def accepted(self) -> bool:
        return self.result == AccessUseResult.ACCEPTED


def _string_id(value):
    return str(value) if value else None


def _emit_access_event(access, *, event_type, previous_status=None, use=None, audit_reason=""):
    suffix = event_type.rsplit(".", 1)[-1]
    if use is not None:
        suffix = f"{suffix}:{use.pk}"
    space_id = getattr(access.activity, "space_id", None)
    payload = {
        "access_id": str(access.pk),
        "activity_id": str(access.activity_id),
        "occurrence_id": _string_id(access.occurrence_id),
        "journey_id": _string_id(access.journey_id),
        "beneficiary_id": _string_id(access.beneficiary_id),
        "issued_by_id": _string_id(access.issued_by_id),
        "previous_status": previous_status,
        "status": access.status,
    }
    if use is not None:
        payload["access_use_id"] = str(use.pk)
    if audit_reason:
        payload["reason"] = (audit_reason or "").strip()[:240]
    return emit_domain_event(
        event_type=event_type,
        source_type="access",
        source_id=access.pk,
        idempotency_key=f"access:{access.pk}:{suffix}",
        space_id=space_id,
        activity_id=access.activity_id,
        payload=payload,
    )


def render_access_credential(credential: AccessCredential) -> str:
    payload = f"{credential.credential_type}|{credential.public_id}|{credential.version}"
    return Signer(salt=ACCESS_CREDENTIAL_SIGNING_SALT).sign(payload)


def _parse_credential_token(token: str):
    try:
        payload = Signer(salt=ACCESS_CREDENTIAL_SIGNING_SALT).unsign((token or "").strip())
        credential_type, public_id, raw_version = payload.split("|", 2)
        return credential_type, uuid.UUID(public_id), int(raw_version)
    except (BadSignature, ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Credential invalide.") from exc


def resolve_access_credential(token: str, *, expected_type=CredentialType.QR) -> AccessCredential:
    credential_type, public_id, version = _parse_credential_token(token)
    if credential_type != expected_type:
        raise ValidationError("Type de credential invalide.")
    try:
        return AccessCredential.objects.select_related("access").get(
            public_id=public_id,
            version=version,
            credential_type=credential_type,
        )
    except AccessCredential.DoesNotExist as exc:
        raise ValidationError("Credential invalide.") from exc


def _validate_scope(*, beneficiary, activity, occurrence, journey):
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError("L’Occurrence appartient à une autre Activity.")
    if journey is not None:
        if journey.activity_id != activity.pk:
            raise ValidationError("La Démarche appartient à une autre Activity.")
        if occurrence is not None and journey.occurrence_id and journey.occurrence_id != occurrence.pk:
            raise ValidationError("L’Occurrence est incohérente avec la Démarche.")
        if beneficiary is None:
            raise ValidationError("Un bénéficiaire individuel est obligatoire.")


def _next_credential_version(access):
    return (
        AccessCredential.objects.filter(access=access).aggregate(value=Max("version"))["value"] or 0
    ) + 1


def _create_credential(access, *, credential_type=CredentialType.QR):
    return AccessCredential.objects.create(
        access=access,
        credential_type=credential_type,
        version=_next_credential_version(access),
    )


@transaction.atomic
def issue_access(
    *,
    beneficiary,
    activity,
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
) -> Access:
    if beneficiary is None:
        raise ValidationError("Un Accès appartient toujours à un bénéficiaire individuel.")
    if journey is not None:
        from journeys.models import Journey

        journey = (
            Journey.objects.select_for_update(of=("self",))
            .select_related("activity", "occurrence")
            .order_by()
            .get(pk=journey.pk)
        )
    _validate_scope(
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        journey=journey,
    )
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
                existing.beneficiary_id != beneficiary.pk
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
        beneficiary=beneficiary,
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
    access.full_clean()
    try:
        access.save()
    except IntegrityError:
        if journey is not None and source_key:
            return Access.objects.get(journey=journey, source_key=source_key)
        raise
    if create_credential and access.status in {AccessStatus.PENDING, AccessStatus.VALID}:
        _create_credential(access)
    _emit_access_event(
        access,
        event_type=DomainEventType.ACCESS_ISSUED,
        audit_reason=audit_reason,
    )
    return access


def _set_access_status(access, status):
    previous_status = access.status
    if previous_status == status:
        return access
    access.status = status
    access._allow_status_transition = True
    access.save(update_fields=["status", "updated_at"])
    event_type = {
        AccessStatus.REVOKED: DomainEventType.ACCESS_REVOKED,
        AccessStatus.EXPIRED: DomainEventType.ACCESS_EXPIRED,
    }.get(status)
    if event_type:
        _emit_access_event(
            access,
            event_type=event_type,
            previous_status=previous_status,
        )
    return access


def _revoke_active_credentials(access, *, status=CredentialStatus.REVOKED, now=None):
    now = now or timezone.now()
    credentials = list(
        AccessCredential.objects.select_for_update(of=("self",))
        .filter(access=access, status=CredentialStatus.ACTIVE)
        .order_by()
    )
    for credential in credentials:
        credential.status = status
        if status == CredentialStatus.REVOKED:
            credential.revoked_at = now
        else:
            credential.expired_at = now
        credential._allow_status_transition = True
        credential.save(update_fields=["status", "revoked_at", "expired_at", "updated_at"])
    return credentials


@transaction.atomic
def rotate_access_credential(*, access, actor=None, credential_type=CredentialType.QR):
    access = Access.objects.select_for_update(of=("self",)).order_by().get(pk=access.pk)
    if access.status not in {AccessStatus.PENDING, AccessStatus.VALID}:
        raise ValidationError("Un Accès non actif ne peut pas recevoir un nouveau credential.")
    if actor is not None:
        if not getattr(actor, "is_authenticated", False) or not can(
            actor,
            PermissionCode.ACTIVITY_ACCESS_MANAGE,
            activity=access.activity,
        ):
            raise PermissionDenied("Vous ne pouvez pas faire tourner ce credential.")
    _revoke_active_credentials(access)
    return _create_credential(access, credential_type=credential_type)


@transaction.atomic
def revoke_access(*, access, actor=None):
    access = Access.objects.select_for_update(of=("self",)).select_related("activity").order_by().get(pk=access.pk)
    if actor is not None and (
        not getattr(actor, "is_authenticated", False)
        or not can(actor, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=access.activity)
    ):
        raise PermissionDenied("Vous ne pouvez pas révoquer cet Accès.")
    if access.status == AccessStatus.REVOKED:
        return access
    _set_access_status(access, AccessStatus.REVOKED)
    _revoke_active_credentials(access)
    return access


@transaction.atomic
def cancel_access(*, access, actor=None):
    access = Access.objects.select_for_update(of=("self",)).select_related("activity").order_by().get(pk=access.pk)
    if actor is not None and (
        not getattr(actor, "is_authenticated", False)
        or not can(actor, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=access.activity)
    ):
        raise PermissionDenied("Vous ne pouvez pas annuler cet Accès.")
    if access.status == AccessStatus.CANCELLED:
        return access
    if access.status == AccessStatus.USED:
        raise ValidationError("Un Accès déjà utilisé ne peut pas être annulé.")
    _set_access_status(access, AccessStatus.CANCELLED)
    _revoke_active_credentials(access)
    return access


@transaction.atomic
def expire_access(*, access, now=None):
    now = now or timezone.now()
    access = Access.objects.select_for_update(of=("self",)).select_related("activity").order_by().get(pk=access.pk)
    if access.status in TERMINAL_ACCESS_STATUSES:
        return access
    if access.valid_until is None or access.valid_until > now:
        return access
    _set_access_status(access, AccessStatus.EXPIRED)
    _revoke_active_credentials(access, status=CredentialStatus.EXPIRED, now=now)
    return access


def expire_due_accesses(*, now=None):
    now = now or timezone.now()
    ids = list(
        Access.objects.filter(valid_until__lte=now)
        .exclude(status__in=TERMINAL_ACCESS_STATUSES)
        .values_list("pk", flat=True)
    )
    count = 0
    for access_id in ids:
        access = Access.objects.get(pk=access_id)
        before = access.status
        access = expire_access(access=access, now=now)
        count += int(access.status != before)
    return count


def _result_message(result):
    return {
        AccessUseResult.ACCEPTED: "Accès autorisé.",
        AccessUseResult.ALREADY_USED: "Accès déjà utilisé.",
        AccessUseResult.EXPIRED: "Accès expiré.",
        AccessUseResult.NOT_YET_VALID: "Accès pas encore valide.",
        AccessUseResult.REVOKED: "Accès révoqué.",
        AccessUseResult.CANCELLED: "Accès annulé.",
        AccessUseResult.WRONG_ACTIVITY: "Accès prévu pour une autre Activity.",
        AccessUseResult.WRONG_OCCURRENCE: "Accès prévu pour une autre Occurrence.",
        AccessUseResult.INVALID_CREDENTIAL: "Credential invalide.",
    }.get(result, "Résultat du contrôle.")


def _controller_actor(controller):
    return controller if getattr(controller, "is_authenticated", False) else None


def _normalize_client_reference(controller, client_reference):
    if _controller_actor(controller) is None:
        return ""
    return (client_reference or "").strip()[:64]


def _existing_idempotent_use(*, access, controller, client_reference):
    actor = _controller_actor(controller)
    client_reference = _normalize_client_reference(controller, client_reference)
    if actor is None or not client_reference:
        return None
    existing = (
        AccessUse.objects.select_related("credential")
        .filter(actor=actor, client_reference=client_reference)
        .order_by("created_at", "id")
        .first()
    )
    if existing is None:
        return None
    if existing.access_id != access.pk:
        raise ValidationError("Cette référence client appartient à un autre contrôle.")
    return existing


def _record_use(
    *,
    access,
    credential,
    controller,
    occurrence,
    result,
    source,
    now,
    client_reference="",
):
    return AccessUse.objects.create(
        access=access,
        credential=credential,
        actor=_controller_actor(controller),
        occurrence=occurrence,
        result=result,
        source=(source or "")[:80],
        client_reference=_normalize_client_reference(controller, client_reference),
        used_at=now,
    )


def _outcome(*, result, message, access=None, credential=None, use=None):
    return AccessValidationOutcome(
        result=result,
        message=message,
        access=access,
        credential=credential,
        use=use,
    )


@transaction.atomic
def validate_access(
    *,
    access,
    credential=None,
    controller=None,
    authority_check=None,
    expected_activity=None,
    expected_occurrence=None,
    source="",
    client_reference="",
    now=None,
) -> AccessValidationOutcome:
    now = now or timezone.now()
    access = (
        Access.objects.select_for_update(of=("self",))
        .select_related("activity", "occurrence", "beneficiary")
        .order_by()
        .get(pk=access.pk)
    )
    locked_credential = None
    if credential is not None:
        locked_credential = (
            AccessCredential.objects.select_for_update(of=("self",))
            .filter(pk=credential.pk, access=access)
            .order_by()
            .first()
        )
        if locked_credential is None:
            return _outcome(result=AccessUseResult.INVALID_CREDENTIAL, message="Credential invalide.", access=access)

    if controller is not None:
        if authority_check is not None:
            authorized = bool(authority_check(controller, access))
        else:
            authorized = getattr(controller, "is_authenticated", False) and can(
                controller,
                PermissionCode.ACTIVITY_ACCESS_MANAGE,
                activity=access.activity,
            )
        if not authorized:
            raise PermissionDenied("Ce contrôleur n’est pas autorisé pour cet Accès.")

    existing_use = _existing_idempotent_use(
        access=access,
        controller=controller,
        client_reference=client_reference,
    )
    if existing_use is not None:
        return _outcome(
            result=existing_use.result,
            message=_result_message(existing_use.result),
            access=access,
            credential=existing_use.credential or locked_credential,
            use=existing_use,
        )

    if locked_credential is not None and locked_credential.status != CredentialStatus.ACTIVE:
        result = {
            AccessStatus.CANCELLED: AccessUseResult.CANCELLED,
            AccessStatus.EXPIRED: AccessUseResult.EXPIRED,
            AccessStatus.REVOKED: AccessUseResult.REVOKED,
            AccessStatus.TRANSFERRED: AccessUseResult.REVOKED,
        }.get(access.status)
        if result is None:
            result = (
                AccessUseResult.EXPIRED
                if locked_credential.status == CredentialStatus.EXPIRED
                else AccessUseResult.REVOKED
            )
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=result,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(
            result=result,
            message=_result_message(result),
            access=access,
            credential=locked_credential,
            use=use,
        )

    if expected_activity is not None and access.activity_id != expected_activity.pk:
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=AccessUseResult.WRONG_ACTIVITY,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=AccessUseResult.WRONG_ACTIVITY, message=_result_message(AccessUseResult.WRONG_ACTIVITY), access=access, credential=locked_credential, use=use)

    if expected_occurrence is not None and access.occurrence_id not in {None, expected_occurrence.pk}:
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=AccessUseResult.WRONG_OCCURRENCE,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=AccessUseResult.WRONG_OCCURRENCE, message=_result_message(AccessUseResult.WRONG_OCCURRENCE), access=access, credential=locked_credential, use=use)

    status_result = {
        AccessStatus.USED: AccessUseResult.ALREADY_USED,
        AccessStatus.REVOKED: AccessUseResult.REVOKED,
        AccessStatus.CANCELLED: AccessUseResult.CANCELLED,
        AccessStatus.EXPIRED: AccessUseResult.EXPIRED,
        AccessStatus.TRANSFERRED: AccessUseResult.REVOKED,
    }.get(access.status)
    if status_result:
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=status_result,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=status_result, message=_result_message(status_result), access=access, credential=locked_credential, use=use)
    if access.status != AccessStatus.VALID:
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=AccessUseResult.CANCELLED,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=AccessUseResult.CANCELLED, message="Accès non actif.", access=access, credential=locked_credential, use=use)
    if access.valid_from and now < access.valid_from:
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=AccessUseResult.NOT_YET_VALID,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=AccessUseResult.NOT_YET_VALID, message=_result_message(AccessUseResult.NOT_YET_VALID), access=access, credential=locked_credential, use=use)
    if access.valid_until and now >= access.valid_until:
        _set_access_status(access, AccessStatus.EXPIRED)
        _revoke_active_credentials(access, status=CredentialStatus.EXPIRED, now=now)
        use = _record_use(
            access=access,
            credential=locked_credential,
            controller=controller,
            occurrence=expected_occurrence,
            result=AccessUseResult.EXPIRED,
            source=source,
            now=now,
            client_reference=client_reference,
        )
        return _outcome(result=AccessUseResult.EXPIRED, message=_result_message(AccessUseResult.EXPIRED), access=access, credential=locked_credential, use=use)

    if access.single_use:
        if AccessUse.objects.filter(access=access, result=AccessUseResult.ACCEPTED).exists():
            _set_access_status(access, AccessStatus.USED)
            use = _record_use(
                access=access,
                credential=locked_credential,
                controller=controller,
                occurrence=expected_occurrence,
                result=AccessUseResult.ALREADY_USED,
                source=source,
                now=now,
                client_reference=client_reference,
            )
            return _outcome(result=AccessUseResult.ALREADY_USED, message=_result_message(AccessUseResult.ALREADY_USED), access=access, credential=locked_credential, use=use)
        _set_access_status(access, AccessStatus.USED)

    use = _record_use(
        access=access,
        credential=locked_credential,
        controller=controller,
        occurrence=expected_occurrence or access.occurrence,
        result=AccessUseResult.ACCEPTED,
        source=source,
        now=now,
        client_reference=client_reference,
    )
    _emit_access_event(
        access,
        event_type=DomainEventType.ACCESS_USED,
        previous_status=AccessStatus.VALID,
        use=use,
    )
    return _outcome(result=AccessUseResult.ACCEPTED, message=_result_message(AccessUseResult.ACCEPTED), access=access, credential=locked_credential, use=use)


def validate_access_credential(
    token: str,
    *,
    controller=None,
    authority_check=None,
    expected_activity=None,
    expected_occurrence=None,
    expected_type=CredentialType.QR,
    source="",
    client_reference="",
    now=None,
):
    try:
        credential = resolve_access_credential(token, expected_type=expected_type)
    except ValidationError:
        return _outcome(result=AccessUseResult.INVALID_CREDENTIAL, message="Credential invalide.")
    return validate_access(
        access=credential.access,
        credential=credential,
        controller=controller,
        authority_check=authority_check,
        expected_activity=expected_activity,
        expected_occurrence=expected_occurrence,
        source=source,
        client_reference=client_reference,
        now=now,
    )