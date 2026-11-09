"""Owner-backed Jour J / Live composition without an exclusive role switch.

A single authenticated viewer may have multiple *independent* relationships to
an Occurrence. Never merge their permissions: each section comes from its owner
resolver and is omitted if that resolver does not authorize the viewer.

This is deliberately additive to the existing personal and operations APIs.
"""
from __future__ import annotations

from authorization.constants import PermissionCode
from journeys.models import Journey
from journeys.collaboration_services import can_access_case
from .occurrence_experience_facts import compose_live_knowledge
from authorization.services import can, has_platform_authority
from core.api.day_of_projection import build_personal_day_of_data
from scanner.permissions import user_can_scan_activity

from .occurrence_live import occurrence_live_phase, resolve_occurrence_live
from .participant_occurrence_live import resolve_participant_occurrence_live
from .permissions import (
    user_can_manage_activity_operations,
    user_can_view_activity_operations,
)


_LIVE_PHASES = {"arrival", "live"}


def _institutional_journeys(*, occurrence, viewer):
    """Shared Journey facts, not duplicated cases or a personal Access grant.

    A Space's members need a current matching mandate; Dossier is optional.
    Only Journeys attached to this actual Occurrence are projected.
    """
    rows = []
    queryset = (
        Journey.objects.filter(
            beneficiary_space__isnull=False,
            activity=occurrence.activity,
            occurrence=occurrence,
        )
        .select_related("beneficiary_space")
        .order_by("created_at", "id")
    )
    for journey in queryset:
        if not can_access_case(viewer, journey):
            continue
        rows.append({
            "id": str(journey.pk),
            "beneficiary": {
                "kind": "space",
                "id": str(journey.beneficiary_space_id),
                "name": journey.beneficiary_space.name,
            },
            "status": journey.status,
            "workflow": journey.workflow,
            "source": "journeys.journey",
        })
    return rows


def _owner_permission(viewer, occurrence, permission, space_permission=None):
    """Do not promote platform-wide authority to an owner-scoped role."""
    if can(
        viewer, permission, activity=occurrence.activity,
        include_platform=False,
    ):
        return True
    return bool(
        space_permission
        and occurrence.activity.space_id
        and can(
            viewer, space_permission, occurrence.activity.space,
            include_platform=False,
        )
    )



def resolve_occurrence_experience(*, occurrence, viewer, surface, observed_at):
    """Return only independently authorized participant and operator sections.

    `viewer` is the authenticated Profile. Space authority is resolved via
    canonical activity/space mandates, not by a client-provided profile/space ID.
    A Space acting as a beneficiary needs its own owner-backed beneficiary
    resolver before any such section can be exposed.
    """
    if surface not in {"day_of", "live"}:
        raise ValueError("Unsupported Occurrence experience surface")
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return None

    phase = occurrence_live_phase(occurrence, now=observed_at)
    if surface == "live" and phase not in _LIVE_PHASES:
        return None

    participant = resolve_participant_occurrence_live(
        occurrence=occurrence, actor=viewer, observed_at=observed_at,
    )
    can_view_operations = user_can_view_activity_operations(
        viewer, occurrence.activity,
    )
    operator = (
        resolve_occurrence_live(
            occurrence=occurrence, actor=viewer, observed_at=observed_at,
        )
        if can_view_operations else None
    )
    # A previous resolver might be extended to return a beneficiary view.
    # Never mistake it for an authorized operator projection.
    if operator is not None and operator.get("perspective") not in {"space", "operator"}:
        operator = None

    scanner_allowed = user_can_scan_activity(
        viewer, occurrence.activity, occurrence=occurrence,
    )
    # These are independent owner permissions; no fictitious finance/logistics
    # actions or URLs are inferred from a permission code.
    finance_allowed = _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_FINANCE_VIEW, PermissionCode.FINANCE_VIEW,
    )
    platform_allowed = has_platform_authority(viewer)
    # Platform supervision is not automatically an organizer relationship.
    owner_operations_allowed = _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_OPERATIONS_VIEW, PermissionCode.SPACE_MANAGE,
    )
    operations_allowed = operator is not None
    operations_manage = user_can_manage_activity_operations(
        viewer, occurrence.activity,
    )
    finance_manage = _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_FINANCE_MANAGE, PermissionCode.FINANCE_MANAGE,
    )
    institutional = _institutional_journeys(
        occurrence=occurrence, viewer=viewer,
    )
    sections = {}
    if participant is not None:
        sections["participant"] = (
            build_personal_day_of_data(
                profile=viewer, occurrence=occurrence, live_payload=participant,
            )
            if surface == "day_of" else participant
        )
    if institutional:
        sections["institutional"] = institutional
    if operations_allowed:
        # Keep platform-only supervision distinct from owner-scoped organization.
        if owner_operations_allowed:
            sections["organizer"] = operator
        elif platform_allowed:
            sections["platform"] = operator

    # Scanner and finance can be held independently of operations-view.
    # Announce only the verified capability, never confidential owner facts.
    capabilities = {}
    if scanner_allowed:
        capabilities["scanner"] = {
            "source": "scanner.permissions",
            "permission": PermissionCode.ACTIVITY_ACCESS_SCAN,
        }
    if finance_allowed:
        capabilities["finance_view"] = {
            "source": "authorization.services",
            "permission": PermissionCode.ACTIVITY_FINANCE_VIEW,
        }
    if operations_manage and (owner_operations_allowed or not platform_allowed):
        capabilities["operations_manage"] = {
            "source": "operations.permissions",
            "permission": PermissionCode.ACTIVITY_OPERATIONS_MANAGE,
        }
    if finance_manage:
        capabilities["finance_manage"] = {
            "source": "authorization.services",
            "permission": PermissionCode.ACTIVITY_FINANCE_MANAGE,
        }
    if operations_allowed and owner_operations_allowed:
        capabilities["operations_view"] = {
            "source": "operations.permissions",
            "permission": PermissionCode.ACTIVITY_OPERATIONS_VIEW,
        }

    if institutional:
        capabilities["institutional_journey_view"] = {
            "source": "journeys.collaboration_services",
            "permission": "journey.case.view",
        }
    if not sections and not capabilities:
        return None

    relations = {
        "participant": participant is not None,
        "institutional_beneficiary": bool(institutional),
        "organizer": bool(owner_operations_allowed or scanner_allowed or finance_allowed or finance_manage or (operations_manage and not platform_allowed)),
        "platform": bool(platform_allowed),
    }
    return {
        "identity": {
            "kind": "occurrence",
            "id": str(occurrence.pk),
        },
        "surface": surface,
        "phase": phase,
        "relations": relations,
        "sections": sections,
        "capabilities": capabilities,
        "presentation": {
            "role_switch_required": False,
            "simultaneous_sections": True,
            "primary_action_limit": None,
        },
        "knowledge": compose_live_knowledge(
            occurrence=occurrence,
            participant=participant,
            operator=operator,
            institutional=institutional,
            observed_at=observed_at,
        ),
        "links": {
            "day_of": (
                f"/api/v1/operations/occurrences/{occurrence.pk}/experience/day-of/"
            ),
            **({
                "live": f"/api/v1/operations/occurrences/{occurrence.pk}/experience/live/",
            } if phase in _LIVE_PHASES else {}),
            **({
                "scanner": f"/api/v1/scanner/occurrences/{occurrence.pk}/context/",
            } if scanner_allowed else {}),
        },
    }
