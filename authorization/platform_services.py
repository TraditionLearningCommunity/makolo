from django.core.exceptions import ValidationError
from django.db import transaction

from .constants import STANDARD_PLATFORM_ROLE_CODES
from .models import AuthorityScope, Mandate, MandateStatus, Role
from .services import get_system_role


def validate_role_for_platform(role: Role) -> None:
    if not role.is_active or role.scope_type != AuthorityScope.PLATFORM or not role.is_system:
        raise ValidationError("Ce rôle ne peut pas être accordé sur la plateforme Makolo.")
    if role.organization_id is not None or role.code not in STANDARD_PLATFORM_ROLE_CODES:
        raise ValidationError("Ce rôle plateforme n'est pas un rôle système pris en charge.")


@transaction.atomic
def grant_platform_role(*, profile, role, granted_by=None, source="platform-service") -> Mandate:
    if isinstance(role, str):
        role = get_system_role(role, scope_type=AuthorityScope.PLATFORM)
    validate_role_for_platform(role)
    existing = (
        Mandate.objects.select_for_update()
        .filter(
            profile=profile,
            role=role,
            scope_type=AuthorityScope.PLATFORM,
            status=MandateStatus.ACTIVE,
        )
        .order_by()
        .first()
    )
    if existing:
        return existing
    mandate = Mandate(
        profile=profile,
        role=role,
        scope_type=AuthorityScope.PLATFORM,
        status=MandateStatus.ACTIVE,
        granted_by=granted_by,
        source=source,
    )
    mandate.full_clean()
    mandate.save()
    return mandate
