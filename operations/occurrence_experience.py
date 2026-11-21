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
from .experience_insights import available_insights
from authorization.services import can, effective_permission_codes, has_platform_authority
from core.api.day_of_projection import build_personal_day_of_data
from scanner.permissions import user_can_scan_activity

from .occurrence_live import occurrence_live_phase, resolve_occurrence_live
from .participant_occurrence_live import resolve_participant_occurrence_live
from .permissions import (
    user_can_manage_activity_operations,
    user_can_view_activity_operations,
)


_LIVE_PHASES = {"arrival", "live"}


def _institutional_journeys(*, occurrence, viewer, actor_space_id=None):
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
    if actor_space_id is not None:
        queryset = queryset.filter(beneficiary_space_id=actor_space_id)
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



def resolve_occurrence_experience(*, occurrence, viewer, surface, observed_at, actor_space_id=None):
    """Return only independently authorized participant and operator sections.

    `viewer` is the authenticated Profile. Space authority is resolved via
    canonical activity/space mandates, not by a client-provided profile/space ID.
    A beneficiary Space is represented by its unique, owner-backed Journey;
    it is not mistaken for a personal admission Access or credential.
    """
    if surface not in {"day_of", "live"}:
        raise ValueError("Unsupported Occurrence experience surface")
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return None
    if actor_space_id is not None:
        # Actor is explicitly a Space, not a switch among business roles.
        # Confirm an actual current non-platform mandate for that Space.
        from organizations.models import Organization

        selected_space = Organization.objects.filter(pk=actor_space_id).first()
        if selected_space is None:
            return None
        space_authority = effective_permission_codes(
            viewer, space=selected_space, include_platform=False,
        )
        # An Activity-scoped operator can act for the owning Space without
        # holding a global Space mandate (e.g. scanner, local operations).
        activity_authority = (
            effective_permission_codes(
                viewer, activity=occurrence.activity, include_platform=False,
            )
            if occurrence.activity.space_id == selected_space.pk else set()
        )
        if not space_authority and not activity_authority:
            return None

    phase = occurrence_live_phase(occurrence, now=observed_at)
    # Live is an explicit per-Occurrence opt-in, never implied by schedule.
    live_available = bool(getattr(occurrence, "live_enabled", False)) and phase in _LIVE_PHASES
    if surface == "live" and not live_available:
        return None

    participant = resolve_participant_occurrence_live(
        occurrence=occurrence, actor=viewer, observed_at=observed_at,
    )
    same_operator_space = (
        actor_space_id is None or
        occurrence.activity.space_id == actor_space_id
    )
    can_view_operations = same_operator_space and user_can_view_activity_operations(
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

    scanner_allowed = same_operator_space and user_can_scan_activity(
        viewer, occurrence.activity, occurrence=occurrence,
    )
    # These are independent owner permissions; no fictitious finance/logistics
    # actions or URLs are inferred from a permission code.
    finance_allowed = same_operator_space and _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_FINANCE_VIEW, PermissionCode.FINANCE_VIEW,
    )
    platform_allowed = has_platform_authority(viewer)
    # Platform supervision is not automatically an organizer relationship.
    owner_operations_allowed = same_operator_space and _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_OPERATIONS_VIEW, PermissionCode.SPACE_MANAGE,
    )
    operations_allowed = operator is not None
    operations_manage = same_operator_space and user_can_manage_activity_operations(
        viewer, occurrence.activity,
    )
    finance_manage = same_operator_space and _owner_permission(
        viewer, occurrence,
        PermissionCode.ACTIVITY_FINANCE_MANAGE, PermissionCode.FINANCE_MANAGE,
    )
    institutional = _institutional_journeys(
        occurrence=occurrence, viewer=viewer, actor_space_id=actor_space_id,
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

    # Cumulative domain rights, not mutually exclusive organizer modes.
    # These do not imply that owner data or a mutation endpoint is available.
    for name, permission in (
        ("access_control_view", PermissionCode.ACTIVITY_ACCESS_VIEW),
        ("access_control_manage", PermissionCode.ACTIVITY_ACCESS_MANAGE),
        ("capacity_view", PermissionCode.ACTIVITY_CAPACITY_VIEW),
        ("capacity_manage", PermissionCode.ACTIVITY_CAPACITY_MANAGE),
        ("commerce_view", PermissionCode.ACTIVITY_COMMERCE_VIEW),
        ("commerce_manage", PermissionCode.ACTIVITY_COMMERCE_MANAGE),
    ):
        if same_operator_space and _owner_permission(viewer, occurrence, permission):
            capabilities[name] = {
                "source": "authorization.services",
                "permission": permission,
            }

    if occurrence.activity.space_id and same_operator_space:
        for name, permission in (
            ("place_view", PermissionCode.SPACE_PLACES_VIEW),
            ("place_manage", PermissionCode.SPACE_PLACES_MANAGE),
        ):
            if can(
                viewer, permission, occurrence.activity.space,
                include_platform=False,
            ):
                capabilities[name] = {
                    "source": "authorization.services",
                    "permission": permission,
                }

    if institutional:
        capabilities["institutional_journey_view"] = {
            "source": "journeys.collaboration_services",
            "permission": "journey.case.view",
        }
    if not sections and not capabilities:
        return None

    # Two legitimate next moves can coexist. Do not invent a mutation from a
    # textual instruction; only owner-backed links become executable handoffs.
    actions = []
    if participant is not None:
        own_action = (participant.get("next_action") or {})
        if own_action.get("type") not in {None, "none"}:
            actions.append({
                "territory": "participant",
                "kind": "instruction",
                "type": own_action.get("type"),
                "label": own_action.get("label"),
                "source": own_action.get("source"),
            })
    if operator is not None and ("organizer" in sections or "platform" in sections):
        operator_action = (operator.get("next_action") or {})
        if operator_action.get("type") not in {None, "none"}:
            actions.append({
                "territory": "organizer" if "organizer" in sections else "platform",
                "kind": "instruction",
                "type": operator_action.get("type"),
                "label": operator_action.get("label"),
                "source": operator_action.get("source"),
            })
    if scanner_allowed:
        actions.append({
            "territory": (
                "organizer"
                if not platform_allowed or owner_operations_allowed
                else "platform"
            ),
            "kind": "owner_handoff",
            "type": "scanner",
            "label": "Ouvrir Scanner",
            "source": "scanner.permissions",
            "url": f"/api/v1/scanner/occurrences/{occurrence.pk}/context/",
        })

    # L5 owner handoffs: each read URL is a real, separately authorized API.
    # Navigation is a new owner check, not a grant inferred from this listing.
    occurrence_base = f"/api/v1/operations/occurrences/{occurrence.pk}"
    depths = []
    def add_depth(kind, label, territory, read_path, source, *, can_manage=False):
        depths.append({
            "kind": kind,
            "label": label,
            "territory": territory,
            "read_path": read_path,
            "source": source,
            "can_manage": bool(can_manage),
        })

    if participant is not None:
        if participant.get("queue"):
            add_depth("my_queue", "Ma file", "participant",
                      f"{occurrence_base}/queues/me/", "operations.queue")
        if participant.get("placement"):
            add_depth("my_placement", "Mon placement", "participant",
                      f"{occurrence_base}/placements/me/", "operations.placement")
        flow = participant.get("flow") or {}
        if flow.get("checkpoints") or flow.get("next_checkpoint"):
            add_depth("my_checkpoints", "Mes étapes", "participant",
                      f"{occurrence_base}/checkpoints/me/", "operations.checkpoint")
        add_depth("readiness", "Ma préparation", "participant",
                  f"{occurrence_base}/readiness/", "readiness")
    if operator is not None and ("organizer" in sections or "platform" in sections):
        add_depth("operator_queue", "Gérer les files", "organizer",
                  f"{occurrence_base}/queues/", "operations.queue",
                  can_manage=operations_manage)
        add_depth("operator_placement", "Gérer les placements", "organizer",
                  f"{occurrence_base}/placement-plans/", "operations.placement",
                  can_manage=operations_manage)
        add_depth("operator_checkpoints", "Gérer les points de contrôle", "organizer",
                  f"{occurrence_base}/checkpoints/", "operations.checkpoint",
                  can_manage=operations_manage)
        if participant is None:
            add_depth("readiness", "Préparation opérationnelle", "organizer",
                      f"{occurrence_base}/readiness/", "readiness")
    depths.extend(available_insights(
        occurrence=occurrence, viewer=viewer,
        organizer_scope=same_operator_space,
    ))
    if scanner_allowed:
        add_depth("scanner", "Scanner les accès", "organizer",
                  f"/api/v1/scanner/occurrences/{occurrence.pk}/context/",
                  "scanner")
    # No incident/media owner linked to this Occurrence has been verified here.
    # Do not advertise fictitious pages or mutable endpoints for those domains.

    relations = {
        "participant": participant is not None,
        "institutional_beneficiary": bool(institutional),
        "organizer": bool(
            owner_operations_allowed or finance_allowed or finance_manage
            or (scanner_allowed and not platform_allowed)
            or (operations_manage and not platform_allowed)
            or (
                not platform_allowed and any(
                    name in capabilities for name in (
                        "access_control_view", "access_control_manage",
                        "capacity_view", "capacity_manage",
                        "commerce_view", "commerce_manage",
                        "place_view", "place_manage",
                    )
                )
            )
        ),
        "platform": bool(platform_allowed),
    }
    return {
        "identity": {
            "kind": "occurrence",
            "id": str(occurrence.pk),
        },
        "context": {
            "viewer_profile_id": str(viewer.pk),
            "actor_space_id": str(actor_space_id) if actor_space_id else None,
            "activity": {"id": str(occurrence.activity_id), "title": occurrence.activity.title},
            "occurrence": {
                "id": str(occurrence.pk),
                "label": occurrence.label or None,
                "state": occurrence.status,
            },
        },
        "surface": surface,
        "phase": phase,
        "live": {
            "available": live_available,
            "enabled": bool(getattr(occurrence, "live_enabled", False)),
            "ends_at": occurrence.end_at.isoformat() if occurrence.end_at else None,
            "reason": None if live_available else (
                "not_enabled" if not getattr(occurrence, "live_enabled", False) else "outside_live_window"
            ),
        },
        "relations": relations,
        "sections": sections,
        "capabilities": capabilities,
        "actions": actions,
        "depths": depths,
        "presentation": {
            "role_switch_required": False,
            "simultaneous_sections": True,
            "primary_action_limit": None,
        },
        "knowledge": compose_live_knowledge(
            occurrence=occurrence,
            participant=participant,
            operator=(operator if ("organizer" in sections or "platform" in sections) else None),
            institutional=institutional,
            observed_at=observed_at,
        ),
        "links": {
            "day_of": (
                f"/api/v1/operations/occurrences/{occurrence.pk}/experience/day-of/"
            ),
            **({
                "live": f"/api/v1/operations/occurrences/{occurrence.pk}/experience/live/",
            } if live_available else {}),
            **({
                "scanner": f"/api/v1/scanner/occurrences/{occurrence.pk}/context/",
            } if scanner_allowed else {}),
        },
    }
