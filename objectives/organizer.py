"""Private, bounded composition for Moi > Mes démarches.

No new business owner: Project and Dossier come from Objectives, Journey from
Journeys. The client stores these scoped, stable identities and builds views
locally; it must never infer a hidden parent from an inaccessible relation.
"""
from __future__ import annotations

from django.urls import reverse

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization
from core.participant_selectors import participant_journeys
from objectives.models import DossierJourneyLink, ProjectDossierLink
from objectives.selectors import dossiers_for_profile, projects_for_profile


def _iso(value):
    return value.isoformat() if value is not None else None


def build_organizer_page(profile, *, limit=50, offset=0, actor_context=None):
    """A synchronized window per kind, with truthful partial-coverage flags.

    Offset is shared for the three independently ordered collections. A page
    may be empty for one kind and populated for another. No global total, hidden
    count or all-descendants assertion is exposed to the client.
    """
    visible_projects = projects_for_profile(profile)
    visible_dossiers = dossiers_for_profile(profile)
    visible_journeys = participant_journeys(profile).prefetch_related(None)
    if actor_context is not None and actor_context.kind == "space":
        visible_projects = actor_context.filter(visible_projects)
        visible_dossiers = actor_context.filter(visible_dossiers)
        # Only Journeys visible to this participant and genuinely linked
        # to visible Dossiers of the selected Space are indexed.
        visible_journeys = visible_journeys.filter(
            dossier_links__is_active=True,
            dossier_links__dossier_id__in=visible_dossiers.values_list("pk", flat=True),
        ).distinct()
    projects = list(visible_projects.order_by("-updated_at", "id")[offset:offset + limit + 1])
    dossiers = list(visible_dossiers.order_by("-updated_at", "id")[offset:offset + limit + 1])
    journeys = list(visible_journeys.order_by("-updated_at", "id")[offset:offset + limit + 1])

    continuation = {
        "project": len(projects) > limit,
        "dossier": len(dossiers) > limit,
        "journey": len(journeys) > limit,
    }
    projects, dossiers, journeys = projects[:limit], dossiers[:limit], journeys[:limit]

    # Parent identities are only disclosed when the viewer can see the parent.
    # A permitted parent not yet acquired on this page is still a parent,
    # not a fictitious "independent" item.
    dossier_ids = [obj.pk for obj in dossiers]
    journey_ids = [obj.pk for obj in journeys]
    # Keep permission scope as SQL subqueries instead of materializing all IDs.
    allowed_project_ids = visible_projects.order_by().values_list("pk", flat=True)
    allowed_dossier_ids = visible_dossiers.order_by().values_list("pk", flat=True)

    project_parent = {}
    for relation in ProjectDossierLink.objects.filter(
        dossier_id__in=dossier_ids, is_active=True,
        project_id__in=allowed_project_ids,
    ).values_list("dossier_id", "project_id"):
        project_parent[str(relation[0])] = str(relation[1])

    journey_parents = {}
    for jid, did in DossierJourneyLink.objects.filter(
        journey_id__in=journey_ids,
        dossier_id__in=allowed_dossier_ids,
        is_active=True,
    ).values_list("journey_id", "dossier_id"):
        journey_parents.setdefault(str(jid), []).append(str(did))

    items = []
    for project in projects:
        space = project.owning_space
        items.append({
            "kind": "project", "id": str(project.pk), "title": project.title,
            "description": project.description or "",
            "state": project.lifecycle,
            "relation": "mine" if project.owner_profile_id == profile.pk else "space" if space is not None else "shared",
            "space": {"name": space.name, "slug": space.slug} if space else None,
            "created_at": _iso(project.created_at),
            "updated_at": _iso(project.updated_at),
            "starts_on": _iso(project.starts_on),
            "ends_on": _iso(project.ends_on),
            "web_url": reverse("objectives:project-detail", kwargs={"project_id": project.pk}),
        })
    for dossier in dossiers:
        space = dossier.owning_space
        items.append({
            "kind": "dossier", "id": str(dossier.pk), "title": dossier.title,
            "description": dossier.description or "",
            "state": dossier.lifecycle,
            "relation": (
                "mine" if dossier.owner_profile_id == profile.pk
                else "space" if space else "shared"
            ),
            "space": {"name": space.name, "slug": space.slug} if space else None,
            "project_id": project_parent.get(str(dossier.pk)),
            "created_at": _iso(dossier.created_at),
            "updated_at": _iso(dossier.updated_at),
            "deadline": _iso(dossier.deadline),
            "web_url": reverse("objectives:dossier-detail", kwargs={"dossier_id": dossier.pk}),
        })
    for journey in journeys:
        items.append({
            "kind": "journey", "id": str(journey.pk),
            "title": journey.activity.title,
            "state": journey.status, "relation": "mine",
            "dossier_ids": journey_parents.get(str(journey.pk), []),
            "created_at": _iso(journey.created_at),
            "updated_at": _iso(journey.updated_at),
            "started_at": _iso(journey.started_at),
            "fulfilled_at": _iso(journey.fulfilled_at),
            "expires_at": _iso(journey.expires_at),
            "web_url": reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
        })

    # The create form must not infer an Espace authority from membership alone.
    # The same server-side services revalidate the selected owner at POST time.
    manageable = space_ids_with_permission(profile, PermissionCode.SPACE_MANAGE)
    spaces = Organization.objects.order_by("name", "id")
    if manageable is not None:
        spaces = spaces.filter(pk__in=manageable)
    if actor_context is not None and actor_context.kind == "space":
        spaces = spaces.filter(slug=actor_context.space_slug)

    return {
        "manageable_spaces": [
            {"id": str(space.pk), "name": space.name}
            for space in spaces[:50]
        ] if offset == 0 else [],
        "actor": {"type": "profile", "id": str(profile.pk)},
        "actor_context": (actor_context.describe() if actor_context
                          else {"kind": "personal"}),
        "items": items,
        "page": {
            "offset": offset,
            "limit": limit,
            "has_more": any(continuation.values()),
            "has_more_by_kind": continuation,
            "next_offset": offset + limit,
        },
    }
