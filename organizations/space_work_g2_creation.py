"""MT4 composition for creating a Programme or real Prestation.

No Programme model, no generic task, no duplicate ServiceDetails owner.
Creation is atomic: if Services specialization fails, the Activity rolls back.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from activities.models import ActivityStatus, ActivityVisibility
from activities.services import create_activity
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import SpaceArchetype
from services.models import ServiceKind
from services.services import create_service_details
from subscriptions.entitlements import resolve_entitlement


G2_ARCHETYPES = {SpaceArchetype.EDUCATION, SpaceArchetype.SERVICE_PROVIDER}
SERVICE_KINDS = {value for value, _ in ServiceKind.choices}


def g2_creation_available(profile, space):
    return (
        space.archetype in G2_ARCHETYPES
        and can(profile, PermissionCode.SPACE_ACTIVITIES_MANAGE, space)
        and resolve_entitlement(space, "activities.create").allowed
    )


@transaction.atomic
def create_g2_owner(*, actor, space, title, short_description="",
                    description="", visibility=ActivityVisibility.PRIVATE,
                    service_kind=None):
    if (
        space.archetype not in G2_ARCHETYPES
        or not can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space)
    ):
        raise PermissionDenied("Autorité Space insuffisante pour cette création.")
    if not isinstance(title, str) or not title.strip():
        raise ValidationError({"title": "Un titre est nécessaire."})
    if visibility not in {value for value, _ in ActivityVisibility.choices}:
        raise ValidationError({"visibility": "Visibilité inconnue."})
    if space.archetype == SpaceArchetype.SERVICE_PROVIDER:
        if service_kind not in SERVICE_KINDS:
            raise ValidationError({"service_kind": "Choisissez un type de service réel."})
    elif service_kind is not None:
        raise ValidationError({"service_kind": "Un Programme n'est pas un Service."})

    activity = create_activity(
        space=space, created_by=actor,
        title=title,
        short_description=short_description or "",
        description=description or "",
        visibility=visibility, status=ActivityStatus.DRAFT,
    )
    service = None
    if space.archetype == SpaceArchetype.SERVICE_PROVIDER:
        # Canonical Services policy/validation; default intake and completion
        # are the existing domain defaults, not new MT4 product states.
        service = create_service_details(
            activity=activity, actor=actor, service_kind=service_kind,
        )
    return activity, service
