"""Viewer-scoped Dossier workspace; one source for web and Flutter.

Composition reads canonical Dossier/Project/Journey/Readiness facts only.
Unlike readiness.visible_items, visible_journeys lists ALL authorized links,
including healthy or fulfilled Journeys. No hidden topology is disclosed.
"""
from __future__ import annotations

from authorization.models import AuthorityScope, Role
from django.urls import reverse
from objectives.models import DossierJourneyDependencyState
from objectives.readiness import resolve_dossier_readiness
from objectives.selectors import (
    active_assignments_for_dossier,
    active_project_for_dossier,
    collaboration_candidates_for_dossier,
    current_dossier_authority_mandates,
    linkable_journeys_for_profile,
    projects_for_profile,
    visible_dependencies_for_profile,
    visible_linked_journeys,
    visible_project_for_dossier,
)
from objectives.services import (
    ALLOWED_LIFECYCLE_TRANSITIONS, can_manage_dossier,
    can_manage_dossier_authority, can_manage_project,
    can_use_journey_for_dossier, dependency_is_satisfied,
)


def _iso(value):
    return value.isoformat() if value is not None else None


def _person(profile):
    return profile.get_full_name().strip() or profile.username


def _choices(queryset, *, label, maximum=50):
    fetched = list(queryset[:maximum + 1])
    return (
        [{"id": str(item.pk), "label": label(item)} for item in fetched[:maximum]],
        len(fetched) > maximum,
    )


def dossier_workspace(viewer, dossier):
    readiness = resolve_dossier_readiness(dossier, viewer=viewer)
    manage = can_manage_dossier(viewer, dossier)
    authority = can_manage_dossier_authority(viewer, dossier)
    visible_project = visible_project_for_dossier(viewer, dossier)
    # The actor must manage BOTH the current Project and the Dossier to move.
    current_project = active_project_for_dossier(dossier) if manage else None
    project_manage = manage and (
        current_project is None or can_manage_project(viewer, current_project)
    )

    attention = {str(item.journey_id): item for item in readiness.visible_items}
    links = list(visible_linked_journeys(viewer, dossier))
    visible_ids = {link.journey_id for link in links}
    journeys = []
    for link in links:
        journey = link.journey
        detail = attention.get(str(journey.pk))
        allowed = manage and can_use_journey_for_dossier(viewer, journey)
        journeys.append({
            "kind": "journey",
            "id": str(journey.pk),
            "link_id": str(link.pk),
            "label": journey.activity.title,
            "state": journey.status,
            "readiness_state": detail.status.value if detail else None,
            "readiness_label": detail.status_label if detail else None,
            "hidden_dependency": bool(detail.hidden_dependency) if detail else False,
            "next_action": {
                "label": detail.next_action.label,
                "state": detail.next_action.reason_code or "action_required",
            } if detail and detail.next_action else None,
            "created_at": _iso(journey.created_at),
            "updated_at": _iso(journey.updated_at),
            # Canonical Journey timestamps: they are instants, not Dossier dates.
            "submitted_at": _iso(journey.submitted_at),
            "confirmed_at": _iso(journey.confirmed_at),
            "started_at": _iso(journey.started_at),
            "fulfilled_at": _iso(journey.fulfilled_at),
            "expires_at": _iso(journey.expires_at),
            "linked_at": _iso(link.linked_at),
            "capabilities": ["unlink"] if allowed else [],
            "web_url": reverse("core:participant-journey-detail",
                               kwargs={"pk": journey.pk}),
        })

    visible_dependencies = list(visible_dependencies_for_profile(viewer, dossier))
    dependencies = []
    for dependency in visible_dependencies:
        if (dependency.dependent_link.journey_id not in visible_ids
                or dependency.required_link.journey_id not in visible_ids):
            continue
        active = dependency.state == DossierJourneyDependencyState.ACTIVE
        can_edit = manage and active and all((
            can_use_journey_for_dossier(viewer, dependency.dependent_link.journey),
            can_use_journey_for_dossier(viewer, dependency.required_link.journey),
        ))
        dependencies.append({
            "id": str(dependency.pk),
            "dependent_link_id": str(dependency.dependent_link_id),
            "required_link_id": str(dependency.required_link_id),
            "dependent_journey_id": str(dependency.dependent_link.journey_id),
            "required_journey_id": str(dependency.required_link.journey_id),
            "state": dependency.state,
            "satisfied": dependency_is_satisfied(dependency) if active else False,
            "effective": (not active or dependency_is_satisfied(dependency)),
            "waiver_reason": dependency.waiver_reason if (manage and not active) else None,
            "capabilities": ["remove", "waive"] if can_edit else [],
        })

    active_assignments = list(active_assignments_for_dossier(dossier))
    assignments = [
        {
            "id": str(item.pk),
            "label": _person(item.assignee) if manage else "Vous",
            "assigned_at": _iso(item.assigned_at),
            "self": item.assignee_id == viewer.pk,
            "capabilities": ["remove"] if manage else [],
        }
        for item in active_assignments
        if manage or item.assignee_id == viewer.pk
    ]
    mandates = []
    if authority:
        mandates = [
            {"id": str(item.pk), "profile": _person(item.profile),
             "role": item.role.name, "capabilities": ["revoke"]}
            for item in current_dossier_authority_mandates(dossier)
        ]

    candidates = {}
    if manage:
        choices, partial = _choices(
            linkable_journeys_for_profile(viewer, dossier=dossier)
            .order_by("-updated_at", "pk"),
            label=lambda item: item.activity.title,
        )
        candidates["journeys"] = choices
        candidates["journeys_partial"] = partial
        responsible, partial = _choices(
            collaboration_candidates_for_dossier(dossier),
            label=_person,
        )
        # Assignments are authorized by the domain service, not membership.
        candidates["assignees"] = [
            item for item in responsible
            if can_manage_dossier(
                next(profile for profile in collaboration_candidates_for_dossier(dossier)
                     if str(profile.pk) == item["id"]), dossier
            )
        ]
        candidates["assignees_partial"] = partial
    if project_manage:
        # Only Projects the viewer can manage are valid destinations.
        eligible = list(projects_for_profile(viewer).select_related(
            "owning_space").order_by("title", "pk")[:101])
        manageable = [
            item for item in eligible if can_manage_project(viewer, item)
        ]
        candidates["projects"] = [
            {"id": str(item.pk), "label": item.title}
            for item in manageable
        ]
        candidates["projects_partial"] = len(eligible) > 100
    if authority:
        people, partial = _choices(
            collaboration_candidates_for_dossier(dossier), label=_person,
        )
        candidates["mandate_profiles"] = people
        candidates["mandate_profiles_partial"] = partial
        roles = Role.objects.filter(
            scope_type=AuthorityScope.DOSSIER,
            is_system=True, is_active=True,
        ).order_by("name", "pk")
        candidates["roles"] = [
            {"id": str(row.pk), "label": row.name}
            for row in roles
        ]

    next_action = None
    if readiness.primary_next_action is not None:
        action = readiness.primary_next_action
        next_action = {
            "label": action.label,
            "journey_id": str(action.journey_id) if action.journey_id else None,
            "state": action.reason_code or "action_required",
        }

    return {
        "identity": {"kind": "dossier", "id": str(dossier.pk)},
        "objective": {"title": dossier.title, "description": dossier.description or None},
        "state": {"code": dossier.lifecycle},
        "deadline": _iso(dossier.deadline),
        "created_at": _iso(dossier.created_at),
        "updated_at": _iso(dossier.updated_at),
        "owner": {
            "kind": "space" if dossier.owning_space_id else "profile",
            "label": dossier.owning_space.name if dossier.owning_space_id
                     else "Dossier personnel",
        },
        "parent_project": {
            "id": str(visible_project.pk), "title": visible_project.title,
            "web_url": reverse("objectives:project-detail",
                               kwargs={"project_id": visible_project.pk}),
        } if visible_project else None,
        "readiness": {
            "state": readiness.status.value if readiness.status else None,
            "label": readiness.status_label,
            "partial": bool(readiness.is_partial),
            "hidden_signal": readiness.hidden_signal,
            "next_action": next_action,
        },
        # All authorized links, not the alert-only readiness.visible_items.
        "visible_items": journeys,
        "visible_dependencies": dependencies,
        "visible_items_complete": True,
        "graph_partial": bool(readiness.is_partial),
        "personal_responsibilities": [
            item for item in assignments if item["self"]
        ],
        "assignments": assignments,
        "mandates": mandates,
        "allowed_transitions": sorted(ALLOWED_LIFECYCLE_TRANSITIONS[dossier.lifecycle])
                               if manage else [],
        "capabilities": (
            (["dossier.edit", "dossier.lifecycle", "dossier.journey.link",
              "dossier.dependency.add", "dossier.assignment.manage"] if manage else [])
            + (["dossier.project.manage"] if project_manage else [])
            + (["dossier.authority.manage"] if authority else [])
        ),
        "candidates": candidates,
        "links": {"self": f"/api/v1/objectives/dossiers/{dossier.pk}/",
                  "actions": f"/api/v1/objectives/dossiers/{dossier.pk}/actions/"},
    }
