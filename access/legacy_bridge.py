from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can

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
    if access.status not in {AccessStatus.PENDING, AccessStatus.VALID}:
        raise ValidationError("Seul un Accès actif peut changer de bénéficiaire.")
    if access.beneficiary_id == beneficiary.pk:
        return access
    access.beneficiary = beneficiary
    access.save(update_fields=["beneficiary", "updated_at"])
    _revoke_active_credentials(access)
    _create_credential(access)
    return access
