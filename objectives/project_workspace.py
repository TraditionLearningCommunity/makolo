"""Authorized Project workspace projection shared by web and Flutter.

Project is a horizon, not a progress counter. Only visible Dossiers and their
authorized readiness facts are projected; no hidden Dossier totals are inferred.
"""
from __future__ import annotations

from django.urls import reverse

from objectives.models import ProjectLifecycle
from objectives.readiness import resolve_dossier_readiness
from objectives.selectors import (
    manageable_dossiers_for_profile,
    projects_for_profile,
    visible_dossiers_for_project,
)
from objectives.services import (
    PROJECT_LIFECYCLE_TRANSITIONS,
    PROJECT_LINKABLE_LIFECYCLES,
    can_manage_dossier,
    can_manage_project,
)


def _date(value):
    return value.isoformat() if value is not None else None


def _dossier_row(dossier, *, actor, project_id, can_manage_parent):
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
        "link": f"/api/v1/objectives/dossiers/{dossier.pk}/",
        "web_url": reverse("objectives:dossier-detail", kwargs={"dossier_id": dossier.pk}),
        "web_actions": ({
            "unlink": reverse("objectives:project-unlink-dossier", kwargs={
                "project_id": project_id,
                "dossier_id": dossier.pk,
            }),
            "move": reverse("objectives:project-move-dossier", kwargs={
                "project_id": dossier.project_links.filter(is_active=True).values_list("project_id", flat=True).first(),
                "dossier_id": dossier.pk,
            }),
        } if manageable else {}),
    }


def project_dossier_page(actor, project, *, offset=0, limit=50):
    # The window and its count are strictly limited to Dossiers visible to actor.
    visible = visible_dossiers_for_project(actor, project)
    chunk = list(visible[offset:offset + limit + 1])
    more = len(chunk) > limit
    manageable = can_manage_project(actor, project)
    items = [
        _dossier_row(dossier, actor=actor, project_id=project.pk, can_manage_parent=manageable)
        for dossier in chunk[:limit]
    ]
    return {
        "actor": {"type": "profile", "id": str(actor.pk)},
        "project_id": str(project.pk),
        "items": items,
        "page": {
            "offset": offset,
            "limit": limit,
            "has_more": more,
            "next_offset": offset + len(items),
        },
    }


def project_workspace(actor, project):
    manageable = can_manage_project(actor, project)
    can_link = manageable and project.lifecycle in PROJECT_LINKABLE_LIFECYCLES
    visible = project_dossier_page(actor, project)
    # Choices are deliberately bounded; the UI explicitly signals partial choices.
    candidates = []
    other_projects = []
    candidates_more = False
    projects_more = False
    if can_link:
        available = list(
            manageable_dossiers_for_profile(actor)
            .exclude(project_links__is_active=True)
            .order_by("title", "id")[:51]
        )
        candidates_more = len(available) > 50
        candidates = [
            {"id": str(row.pk), "title": row.title}
            for row in available[:50]
        ]
    if manageable:
        eligible = list(
            projects_for_profile(actor)
            .filter(lifecycle__in=PROJECT_LINKABLE_LIFECYCLES)
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
        "horizon": {
            "title": project.title,
            "description": project.description or None,
            "starts_on": _date(project.starts_on),
            "ends_on": _date(project.ends_on),
        },
        "state": {"code": project.lifecycle},
        "owner": {
            "kind": "space" if project.owning_space_id else "profile",
            "label": project.owning_space.name if project.owning_space_id else "Projet personnel",
        },
        "visible_dossiers": visible["items"],
        "dossiers_page": visible["page"],
        "allowed_transitions": allowed_transitions,
        "capabilities": (
            ["project.edit", "project.lifecycle", "project.dossier.create",
             "project.dossier.link"] if can_link
            else ["project.edit", "project.lifecycle"] if manageable else []
        ),
        "link_candidates": candidates,
        "link_candidates_partial": candidates_more,
        "move_targets": other_projects,
        "move_targets_partial": projects_more,
        "links": {
            "self": f"/api/v1/objectives/projects/{project.pk}/",
            "dossiers": f"/api/v1/objectives/projects/{project.pk}/dossiers/",
        },
    }
