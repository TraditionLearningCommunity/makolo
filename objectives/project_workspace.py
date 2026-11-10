"""Authorized Project workspace projection shared by web and Flutter.

Project is a horizon, not a progress counter. Only visible Dossiers and their
authorized readiness facts are projected; no hidden Dossier totals are inferred.
"""
from __future__ import annotations

from django.urls import reverse
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Role
from authorization.selectors import current_mandates
from authorization.services import can

from objectives.readiness import resolve_dossier_readiness
from objectives.selectors import (
    active_assignments_for_dossier,
    collaboration_candidates_for_dossier,
    manageable_dossiers_for_profile,
    projects_for_profile,
    visible_dossiers_for_project,
)
from objectives.services import (
    PROJECT_LIFECYCLE_TRANSITIONS,
    PROJECT_LINKABLE_LIFECYCLES,
    can_manage_dossier,
    can_manage_project,
    can_manage_project_authority,
)


def _date(value):
    return value.isoformat() if value is not None else None


def _dossier_row(dossier, *, actor, project_id, can_manage_parent, actor_context=None):
    readiness = resolve_dossier_readiness(dossier, viewer=actor)
    manageable = can_manage_parent and can_manage_dossier(actor, dossier)
    return {
        "kind": "dossier",
        "id": str(dossier.pk),
        "title": dossier.title,
        "description": dossier.description or None,
        "state": dossier.lifecycle,
        "deadline": _date(dossier.deadline),
        "created_at": _date(dossier.created_at),
        "updated_at": _date(dossier.updated_at),
        "readiness": {
            "state": readiness.status.value if readiness.status is not None else None,
            "label": readiness.status_label,
            "partial": bool(readiness.is_partial),
            "hidden_signal": readiness.hidden_signal,
        },
        "capabilities": ["unlink", "move"] if manageable else [],
        "link": (f"/api/v1/objectives/dossiers/{dossier.pk}/"
                 + (actor_context.query_suffix() if actor_context else "")),
        "web_url": reverse("objectives:dossier-detail", kwargs={"dossier_id": dossier.pk}),
        "web_actions": ({
            "unlink": reverse("objectives:project-unlink-dossier", kwargs={
                "project_id": project_id,
                "dossier_id": dossier.pk,
            }),
            "move": reverse("objectives:project-move-dossier", kwargs={
                "project_id": project_id,
                "dossier_id": dossier.pk,
            }),
        } if manageable else {}),
    }


def project_dossier_page(actor, project, *, offset=0, limit=50, actor_context=None):
    # The window and its count are limited to the authorized actor AND the
    # selected Space lens. A linked Dossier from another Space stays hidden.
    visible = visible_dossiers_for_project(actor, project)
    if actor_context is not None:
        visible = actor_context.filter(visible)
    chunk = list(visible[offset:offset + limit + 1])
    more = len(chunk) > limit
    manageable = can_manage_project(actor, project)
    items = [
        _dossier_row(
            dossier, actor=actor, project_id=project.pk,
            can_manage_parent=manageable, actor_context=actor_context,
        )
        for dossier in chunk[:limit]
    ]
    return {
        "actor": {"type": "profile", "id": str(actor.pk)},
        "actor_context": (actor_context.describe(project) if actor_context
                          else {"kind": "personal"}),
        "project_id": str(project.pk),
        "items": items,
        "page": {
            "offset": offset,
            "limit": limit,
            "has_more": more,
            "next_offset": offset + len(items),
        },
    }


def _person(profile):
    return profile.get_full_name().strip() or profile.username


def _project_collaboration(actor, project, dossiers, *, partial):
    """Viewer-aware composition: a Project mandate is not a Dossier assignment.

    Dossier collaborators are disclosed only where Dossier itself permits their
    disclosure. No hidden Dossier, Journey, participant or total is inferred.
    """
    authority = can_manage_project_authority(actor, project)
    current = current_mandates().filter(
        scope_type=AuthorityScope.PROJECT, project=project,
    ).select_related("profile", "role").order_by("granted_at", "pk")
    members = []
    for mandate in current:
        if not authority and mandate.profile_id != actor.pk:
            continue
        members.append({
            "id": str(mandate.pk),
            "profile_id": str(mandate.profile_id),
            "label": _person(mandate.profile) if authority else "Vous",
            "role": mandate.role.name,
            "role_code": mandate.role.code,
            "self": mandate.profile_id == actor.pk,
            "capabilities": ["revoke"] if authority else [],
        })
    contributors = {}
    candidates = {}
    for dossier in dossiers:
        manageable = can_manage_dossier(actor, dossier)
        for assignment in active_assignments_for_dossier(dossier):
            if not manageable and assignment.assignee_id != actor.pk:
                continue
            key = str(assignment.assignee_id)
            contributor = contributors.setdefault(key, {
                "profile_id": key,
                "label": _person(assignment.assignee) if manageable else "Vous",
                "dossier_ids": [],
            })
            contributor["dossier_ids"].append(str(dossier.pk))
        if authority and manageable:
            # Reuse the same bounded, authorized list as Dossier collaboration.
            for person in collaboration_candidates_for_dossier(dossier)[:51]:
                if person.is_active and person.pk != project.owner_profile_id:
                    candidates[str(person.pk)] = {
                        "id": str(person.pk), "label": _person(person),
                    }
    return {
        "members": members,
        "contributors": list(contributors.values()),
        "contributors_partial": bool(partial),
        "candidate_profiles": list(candidates.values())[:50] if authority else [],
        "candidate_profiles_partial": len(candidates) > 50 if authority else False,
        "roles": [
            {"code": role.code, "label": role.name}
            for role in Role.objects.filter(
                scope_type=AuthorityScope.PROJECT, is_system=True, is_active=True,
            ).order_by("name") if role.code in {
                "project-viewer", "project-manager", "project-admin",
            }
        ] if authority else [],
        "can_manage_authority": authority,
    }


def project_workspace(actor, project, *, actor_context=None):
    manageable = can_manage_project(actor, project)
    can_link = manageable and project.lifecycle in PROJECT_LINKABLE_LIFECYCLES
    can_create = can_link and (
        project.owner_profile_id == actor.pk
        or can(actor, PermissionCode.PLATFORM_MANAGE)
        or bool(project.owning_space_id and can(
            actor, PermissionCode.SPACE_MANAGE, space=project.owning_space,
        ))
    )
    visible = project_dossier_page(
        actor, project, actor_context=actor_context,
    )
    collaboration_dossiers = visible_dossiers_for_project(actor, project)
    if actor_context is not None:
        collaboration_dossiers = actor_context.filter(collaboration_dossiers)
    collaboration = _project_collaboration(
        actor, project, collaboration_dossiers[:50],
        partial=visible["page"]["has_more"],
    )
    # Choices are deliberately bounded; the UI explicitly signals partial choices.
    candidates = []
    other_projects = []
    candidates_more = False
    projects_more = False
    if can_link:
        independent = manageable_dossiers_for_profile(actor)
        if actor_context is not None:
            independent = actor_context.filter(independent)
        available = list(
            independent.exclude(project_links__is_active=True)
            .order_by("title", "id")[:51]
        )
        candidates_more = len(available) > 50
        candidates = [
            {"id": str(row.pk), "title": row.title}
            for row in available[:50]
        ]
    if manageable:
        destinations = projects_for_profile(actor)
        if actor_context is not None:
            destinations = actor_context.filter(destinations)
        eligible = list(
            destinations.filter(lifecycle__in=PROJECT_LINKABLE_LIFECYCLES)
            .exclude(pk=project.pk)
            .order_by("title", "id")[:101]
        )
        allowed = [row for row in eligible if can_manage_project(actor, row)]
        projects_more = len(eligible) > 100
        other_projects = [
            {"id": str(row.pk), "title": row.title}
            for row in allowed[:100]
        ]
    allowed_transitions = (
        sorted(PROJECT_LIFECYCLE_TRANSITIONS[project.lifecycle])
        if manageable else []
    )
    return {
        "identity": {"kind": "project", "id": str(project.pk)},
        "viewer": {"kind": "profile", "id": str(actor.pk)},
        "actor_context": (actor_context.describe(project) if actor_context
                          else {"kind": "personal"}),
        "horizon": {
            "title": project.title,
            "description": project.description or None,
            "starts_on": _date(project.starts_on),
            "ends_on": _date(project.ends_on),
        },
        "state": {"code": project.lifecycle},
        "owner": {
            "kind": "space" if project.owning_space_id else "profile",
            "id": str(project.owning_space_id or project.owner_profile_id),
            "label": project.owning_space.name if project.owning_space_id else "Projet personnel",
            "holder": _person(project.owner_profile) if project.owner_profile_id else None,
            **({"slug": project.owning_space.slug}
               if project.owning_space_id else {}),
        },
        "visible_dossiers": visible["items"],
        "dossiers_page": visible["page"],
        "allowed_transitions": allowed_transitions,
        "capabilities": (
            (["project.edit", "project.lifecycle"] if manageable else [])
            + (["project.dossier.link"] if can_link else [])
            + (["project.dossier.create"] if can_create else [])
            + (["project.authority.manage"] if collaboration["can_manage_authority"] else [])
        ),
        "collaboration": collaboration,
        "link_candidates": candidates,
        "link_candidates_partial": candidates_more,
        "move_targets": other_projects,
        "move_targets_partial": projects_more,
        "links": {
            "self": (f"/api/v1/objectives/projects/{project.pk}/"
                     + (actor_context.query_suffix() if actor_context else "")),
            "dossiers": (f"/api/v1/objectives/projects/{project.pk}/dossiers/"
                         + (actor_context.query_suffix() if actor_context else "")),
        },
    }
