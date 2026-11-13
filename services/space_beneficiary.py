"""Authority boundary for a Space *requesting* a Service.

Provider Activity roles never grant authority over the applicant Space.
Read and write are separate; membership, Assignment and current UI context
are not an implied mandate. Called on every request, including replay.
"""

from django.core.exceptions import PermissionDenied

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import SpaceLifecycle
from journeys.models import WorkflowKind


def can_read_space_service(actor, space):
    if space is None or space.lifecycle != SpaceLifecycle.ACTIVE:
        return False
    return any((
        can(actor, PermissionCode.SPACE_ACTIVITIES_VIEW, space, include_platform=False),
        can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space, include_platform=False),
        can(actor, PermissionCode.SPACE_MANAGE, space, include_platform=False),
    ))


def can_act_for_space(actor, space):
    if space is None or space.lifecycle != SpaceLifecycle.ACTIVE:
        return False
    return (
        can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space, include_platform=False)
        or can(actor, PermissionCode.SPACE_MANAGE, space, include_platform=False)
    )


def can_read_space_service_journey(actor, journey):
    return bool(
        journey.workflow == WorkflowKind.SERVICE
        and journey.beneficiary_space_id
        and can_read_space_service(actor, journey.beneficiary_space)
    )


def can_act_for_space_service_journey(actor, journey):
    return bool(
        journey.workflow == WorkflowKind.SERVICE
        and journey.beneficiary_space_id
        and can_act_for_space(actor, journey.beneficiary_space)
    )


def require_space_service_action(actor, journey):
    if not can_act_for_space_service_journey(actor, journey):
        raise PermissionDenied("Mandat Espace insuffisant pour cette demande.")
