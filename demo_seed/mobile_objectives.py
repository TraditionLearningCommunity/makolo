"""Dense canonical Project/Dossier/Journey demo for Moi > Mes démarches.

Only the existing Mobile Mature synthetic persona is targeted. The seed is
idempotent, uses stable IDs for its Objective owners, and invokes canonical
services for relationships, dependencies and lifecycle changes.
"""
from __future__ import annotations

from datetime import timedelta

from journeys.models import Journey
from objectives.models import (
    Dossier, DossierJourneyDependency, DossierJourneyDependencyState,
    DossierLifecycle, Project, ProjectDossierLink, ProjectLifecycle,
)
from objectives.services import (
    add_dependency, link_dossier_to_project, link_journey,
    set_dossier_lifecycle, set_project_lifecycle,
)

from .common import SeedContext, stable_uuid


PROJECT_SPECS = (
    ("Mobilité professionnelle et nouveaux horizons", (
        "Préparer les documents de voyage",
        "Organiser les déplacements professionnels",
        "Constituer le budget de mobilité",
        "Préparer l’arrivée et les rendez-vous",
    )),
    ("Développer une activité indépendante", (
        "Clarifier l’offre de services",
        "Préparer les démarches administratives",
        "Organiser les premiers clients",
        "Sécuriser les moyens de travail",
    )),
    ("Parcours de formation et compétences", (
        "Choisir la formation adaptée",
        "Préparer une candidature",
        "Financer le parcours",
        "Suivre les sessions et attestations",
    )),
    ("Documents essentiels et vie quotidienne", (
        "Renouveler les pièces utiles",
        "Organiser la santé et les rendez-vous",
        "Assurer les services du domicile",
        "Classer les justificatifs importants",
    )),
    ("Vie culturelle et rencontres", (
        "Préparer les événements de l’année",
        "Retrouver les rencontres professionnelles",
        "Organiser les visites en famille",
        "Conserver les souvenirs et les accès",
    )),
    ("Préparer un engagement associatif", (
        "Explorer les initiatives locales",
        "Planifier les actions collectives",
        "Rassembler les partenaires",
        "Faire le bilan des réalisations",
    )),
)

INDEPENDENT_DOSSIERS = (
    "Mettre à jour mon dossier administratif",
    "Préparer un achat important",
    "Faire le point sur mes démarches en attente",
    "Conserver les documents de référence",
)

# Status variety is deliberately independent from the linked Journey statuses.
# A Project is a horizon, a Dossier an outcome, and Journey owns its workflow.
PROJECT_STATES = (
    ProjectLifecycle.ACTIVE, ProjectLifecycle.ACTIVE,
    ProjectLifecycle.DRAFT, ProjectLifecycle.ACTIVE,
    ProjectLifecycle.COMPLETED, ProjectLifecycle.ARCHIVED,
)
DOSSIER_STATES = (
    DossierLifecycle.ACTIVE, DossierLifecycle.ACTIVE,
    DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE,
    DossierLifecycle.COMPLETED, DossierLifecycle.ACTIVE,
    DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE,
    DossierLifecycle.ARCHIVED, DossierLifecycle.ACTIVE,
    DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE,
    DossierLifecycle.ACTIVE, DossierLifecycle.CANCELLED,
    DossierLifecycle.ACTIVE, DossierLifecycle.DRAFT,
    DossierLifecycle.ACTIVE, DossierLifecycle.COMPLETED,
    DossierLifecycle.ACTIVE, DossierLifecycle.DRAFT,
    DossierLifecycle.ACTIVE, DossierLifecycle.ACTIVE,
    DossierLifecycle.ARCHIVED, DossierLifecycle.DRAFT,
    DossierLifecycle.ACTIVE, DossierLifecycle.DRAFT,
    DossierLifecycle.ACTIVE, DossierLifecycle.COMPLETED,
)


def _transition_project(actor, project, target):
    if target == ProjectLifecycle.DRAFT or project.lifecycle == target:
        return
    if project.lifecycle == ProjectLifecycle.DRAFT:
        project = set_project_lifecycle(
            actor=actor, project=project, lifecycle=ProjectLifecycle.ACTIVE,
        )
    if target != ProjectLifecycle.ACTIVE and project.lifecycle == ProjectLifecycle.ACTIVE:
        project = set_project_lifecycle(
            actor=actor, project=project, lifecycle=target,
        )


def _transition_dossier(actor, dossier, target):
    if target == DossierLifecycle.DRAFT or dossier.lifecycle == target:
        return
    if target in (DossierLifecycle.ACTIVE, DossierLifecycle.COMPLETED):
        if dossier.lifecycle == DossierLifecycle.DRAFT:
            dossier = set_dossier_lifecycle(
                actor=actor, dossier=dossier, lifecycle=DossierLifecycle.ACTIVE,
            )
    if target != DossierLifecycle.ACTIVE and dossier.lifecycle != target:
        if target in (DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED):
            # Draft -> cancelled / archived and active -> cancelled / archived
            # are both canonical lifecycle transitions.
            dossier = set_dossier_lifecycle(
                actor=actor, dossier=dossier, lifecycle=target,
            )
        elif target == DossierLifecycle.COMPLETED:
            set_dossier_lifecycle(
                actor=actor, dossier=dossier, lifecycle=target,
            )


def seed_mobile_objectives(ctx: SeedContext, *, primary) -> None:
    """Extend an already seeded Mobile Mature universe.

    Executed inside the parent command's transaction; no synthetic account,
    Activity, Journey or parallel owner model is created here.
    """
    journeys = list(
        Journey.objects.filter(
            beneficiary=primary,
            activity__slug__startswith="mobile-mature-",
        ).select_related("activity").order_by("activity__slug", "pk")
    )
    if len(journeys) < 24:
        raise ValueError("Seed Mobile Mature Journeys before Objectives.")

    projects = []
    for idx, (title, _) in enumerate(PROJECT_SPECS):
        project, _ = Project.objects.get_or_create(
            pk=stable_uuid(f"objectives.project:mobile-mature-{idx}"),
            defaults={
                "title": title,
                "description": "Un horizon personnel composé de plusieurs résultats concrets.",
                "owner_profile": primary,
                "created_by": primary,
                "starts_on": (ctx.as_of - timedelta(days=60 + idx * 22)).date(),
                "ends_on": (ctx.as_of + timedelta(days=130 + idx * 35)).date(),
            },
        )
        if project.owner_profile_id != primary.pk:
            raise ValueError("Mobile Mature Project ownership mismatch.")
        projects.append(project)

    dossier_rows = [
        (project_index, title)
        for project_index, (_, titles) in enumerate(PROJECT_SPECS)
        for title in titles
    ] + [(None, title) for title in INDEPENDENT_DOSSIERS]

    for idx, (project_index, title) in enumerate(dossier_rows):
        dossier, _ = Dossier.objects.get_or_create(
            pk=stable_uuid(f"objectives.dossier:mobile-mature-{idx}"),
            defaults={
                "title": title,
                "description": "Un résultat à organiser avec les démarches réellement engagées.",
                "owner_profile": primary,
                "created_by": primary,
                "deadline": (ctx.as_of + timedelta(days=(idx - 7) * 14)).date(),
            },
        )
        if dossier.owner_profile_id != primary.pk:
            raise ValueError("Mobile Mature Dossier ownership mismatch.")

        if project_index is not None:
            project = projects[project_index]
            active = ProjectDossierLink.objects.filter(
                dossier=dossier, is_active=True,
            ).first()
            if active is None:
                link_dossier_to_project(actor=primary, project=project, dossier=dossier)
            elif active.project_id != project.pk:
                raise ValueError("Demo Dossier was moved to an unexpected Project.")

        # Include genuine independent Dossiers and some empty Dossiers: they
        # expose different Card/List/Explorer states without fabricated tasks.
        linked = []
        if idx % 7 != 3:
            for step in range(2 + idx % 3):
                journey = journeys[(idx * 2 + step) % len(journeys)]
                linked.append(link_journey(
                    actor=primary, dossier=dossier, journey=journey,
                ))

        if (
            len(linked) >= 2
            and DOSSIER_STATES[idx] == DossierLifecycle.ACTIVE
            and idx % 2 == 0
        ):
            dependent, required = linked[1], linked[0]
            exists = DossierJourneyDependency.objects.filter(
                dossier=dossier,
                dependent_link=dependent,
                required_link=required,
                state=DossierJourneyDependencyState.ACTIVE,
            ).exists()
            if not exists:
                add_dependency(
                    actor=primary, dossier=dossier,
                    dependent_link=dependent, required_link=required,
                )

        _transition_dossier(primary, dossier, DOSSIER_STATES[idx])

    # Close historical Projects only after linking all their Dossiers.
    # Existing links remain stable when the seed is re-executed.
    for idx, project in enumerate(projects):
        _transition_project(primary, project, PROJECT_STATES[idx])

    ctx.add("mobile_mature_projects", len(PROJECT_SPECS))
    ctx.add("mobile_mature_dossiers", len(dossier_rows))
