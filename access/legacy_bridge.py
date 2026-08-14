from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import Access, AccessStatus, CredentialStatus
from .services import _create_credential, _revoke_active_credentials, _set_access_status


def _can_manage(actor, activity):
    return bool(
        getattr(actor, "is_authenticated", False)
        and (
            can(actor, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=activity)
            or can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
        )
    )


def _emit_transfer(access, *, previous_beneficiary_id, source):
    if source == "legacy_backfill":
        return None
    return emit_domain_event(
        event_type=DomainEventType.ACCESS_TRANSFERRED,
        source_type="access",
        source_id=access.pk,
        idempotency_key=f"access:{access.pk}:transferred:{access.beneficiary_id}",
        space_id=getattr(access.activity, "space_id", None),
        activity_id=access.activity_id,
        payload={
            "access_id": str(access.pk),
            "activity_id": str(access.activity_id),
            "occurrence_id": str(access.occurrence_id) if access.occurrence_id else None,
            "journey_id": str(access.journey_id) if access.journey_id else None,
            "previous_beneficiary_id": str(previous_beneficiary_id) if previous_beneficiary_id else None,
            "beneficiary_id": str(access.beneficiary_id),
            "status": access.status,
        },
    )


@transaction.atomic
def sync_legacy_access_status(*, access, status, source="legacy_bridge"):
    if status not in AccessStatus.values:
        raise ValidationError("État Access legacy inconnu.")
    access = (
        Access.objects.select_for_update(of=("self",))
        .select_related("activity", "occurrence", "journey", "beneficiary")
        .order_by()
        .get(pk=access.pk)
    )
    if access.status == status:
        return access
    if status == AccessStatus.VALID and access.status not in {AccessStatus.PENDING, AccessStatus.VALID}:
        raise ValidationError("Le bridge legacy ne peut pas réactiver un Accès terminal.")
    _set_access_status(access, status)
    if status in {
        AccessStatus.CANCELLED,
        AccessStatus.REVOKED,
        AccessStatus.EXPIRED,
        AccessStatus.TRANSFERRED,
    }:
        credential_status = (
            CredentialStatus.EXPIRED if status == AccessStatus.EXPIRED else CredentialStatus.REVOKED
        )
        _revoke_active_credentials(access, status=credential_status)
    return access


@transaction.atomic
def transfer_access_beneficiary(*, access, beneficiary, actor=None, source="transfer"):
    if beneficiary is None:
        raise ValidationError("Le nouveau bénéficiaire individuel est obligatoire.")
    access = (
        Access.objects.select_for_update(of=("self",))
        .select_related("activity", "beneficiary")
        .order_by()
        .get(pk=access.pk)
    )
    if actor is not None and not _can_manage(actor, access.activity):
        raise PermissionDenied("Vous ne pouvez pas transférer cet Accès.")
    if access.beneficiary_id == beneficiary.pk:
        return access

    previous_beneficiary_id = access.beneficiary_id
    if access.status in {AccessStatus.PENDING, AccessStatus.VALID}:
        access.beneficiary = beneficiary
        access.save(update_fields=["beneficiary", "updated_at"])
        _revoke_active_credentials(access)
        _create_credential(access)
        _emit_transfer(
            access,
            previous_beneficiary_id=previous_beneficiary_id,
            source=source,
        )
        return access

    if source not in {"ticket_transfer", "ticket_bridge", "legacy_backfill"}:
        raise ValidationError("Seul un Accès actif peut changer de bénéficiaire.")

    # Compatibility-only synchronization for historical Ticket rows that are
    # already terminal. No new right is created: ownership is aligned and any
    # remaining bearer representation is revoked without issuing a fresh one.
    access.beneficiary = beneficiary
    access.save(update_fields=["beneficiary", "updated_at"])
    _revoke_active_credentials(access)
    _emit_transfer(
        access,
        previous_beneficiary_id=previous_beneficiary_id,
        source=source,
    )
    return access
