"""Objectives demo scenarios for the existing scripts.demo_generation orchestrator.

A Project is an owner-managed horizon; Dossier is a concrete result; Journey
remains the canonical activity workflow. No parallel task or synthetic Journey
is invented by this module. The caller chooses authorized demo users.
"""
from collections import Counter
from time import sleep

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections, transaction
from django.db.utils import OperationalError

from journeys.models import Journey
from objectives.models import (
    Dossier, DossierJourneyDependency, DossierJourneyLink, Project,
    ProjectDossierLink,
)
from objectives.services import (
    add_dependency, create_dossier, create_project, link_dossier_to_project,
    link_journey, set_dossier_lifecycle, set_project_lifecycle,
)
from .editorial import objective_titles
from .scope import synthetic_journey_activity_prefixes


# Stable human copy, no technical demo prefix in the UI.
PROJECT_THEMES = (
    ("mon parcours de formation", (
        "Choisir une formation", "Préparer mon inscription",
        "Organiser les sessions", "Réunir les attestations",
        "Faire le point sur les acquis", "Préparer la suite",
    )),
    ("ma mobilité professionnelle", (
        "Préparer les déplacements", "Réunir les documents de voyage",
        "Organiser les rendez-vous", "Comparer les possibilités",
        "Préparer le budget", "Confirmer les réservations",
    )),
    ("mon activité indépendante", (
        "Clarifier les services", "Préparer les démarches administratives",
        "Organiser les premiers clients", "Sécuriser les équipements",
        "Préparer les partenariats", "Suivre les engagements",
    )),
    ("la vie quotidienne", (
        "Mettre à jour mes documents", "Préparer un achat important",
        "Organiser les services essentiels", "Retrouver les justificatifs",
        "Préparer les rendez-vous", "Faire le bilan",
    )),
    ("mes engagements collectifs", (
        "Explorer les initiatives", "Préparer les rencontres",
        "Réunir les informations utiles", "Organiser les contributions",
        "Préparer les activités", "Conserver les comptes rendus",
    )),
    ("mes projets à moyen terme", (
        "Définir les étapes", "Réunir les ressources nécessaires",
        "Prendre les premiers contacts", "Préparer les démarches",
        "Vérifier les conditions", "Organiser la prochaine phase",
    )),
    ("mon développement personnel", (
        "Choisir les priorités", "Organiser les apprentissages",
        "Préparer les activités", "Réunir les ressources",
        "Planifier les rendez-vous", "Suivre les progrès",
    )),
    ("une initiative culturelle", (
        "Préparer les rencontres", "Organiser les visites",
        "Découvrir les possibilités", "Réunir les partenaires",
        "Préparer les ressources", "Conserver les documents",
    )),
)
INDEPENDENT_TITLES = (
    "Régler une question administrative",
    "Préparer un rendez-vous important",
    "Organiser une demande ponctuelle",
    "Conserver les documents utiles",
    "Préparer un déplacement particulier",
    "Suivre une démarche indépendante",
)


def planned_titles(owner, projects, per_project, independent):
    """Deterministic names; reuse the community generator's original pair."""
    legacy_dossier, legacy_project = objective_titles(owner)
    rotation = int(str(owner.pk).replace("-", "")[:6], 16) % len(PROJECT_THEMES)
    for project_idx in range(projects):
        theme, dossier_titles = PROJECT_THEMES[
            (rotation + project_idx) % len(PROJECT_THEMES)
        ]
        project_title = legacy_project if project_idx == 0 else (
            "Développer " + theme
        )
        dossiers = [
            legacy_dossier if project_idx == 0 and idx == 0
            else f"{dossier_titles[idx]} — {theme}"
            for idx in range(per_project)
        ]
        yield project_title, dossiers
    if independent:
        yield None, list(INDEPENDENT_TITLES[:independent])


def _visible_demo_journeys(owner):
    # Never fabricate a Journey or borrow another Profile's one. Both the
    # world and Mobile Mature corpora have explicit synthetic provenance.
    from django.db.models import Q

    prefixes = synthetic_journey_activity_prefixes(owner)
    if not prefixes:
        return []
    activities = Q()
    for prefix in prefixes:
        activities |= Q(activity__slug__startswith=prefix)
    return list(Journey.objects.filter(
        activities, beneficiary=owner,
    ).select_related("activity").order_by("id")[:100])


def _find_project(owner, title):
    return Project.objects.filter(
        owner_profile=owner, title=title,
    ).order_by("pk").first()


def _find_dossier(owner, title):
    return Dossier.objects.filter(
        owner_profile=owner, title=title,
    ).order_by("pk").first()


def _apply_one_profile(owner, profile_plan, journeys, journeys_per_dossier):
    """Write one owner graph atomically; retries must start outside this block."""
    profile_stats = Counter()
    with transaction.atomic():
        sequence = 0
        for project_index, (project_title, dossier_titles) in enumerate(profile_plan):
            project = None
            if project_title is not None:
                project = _find_project(owner, project_title)
                if project is None:
                    project = create_project(
                        actor=owner, owner_profile=owner,
                        title=project_title,
                        description="Un horizon composé de résultats concrets.",
                    )
                    profile_stats["projects_created"] += 1
                    # An active horizon is not a claim of external success.
                    if project_index % 3 != 2:
                        set_project_lifecycle(
                            actor=owner, project=project, lifecycle="active",
                        )
                else:
                    profile_stats["projects_existing"] += 1

            for dossier_index, title in enumerate(dossier_titles):
                dossier = _find_dossier(owner, title)
                if dossier is None:
                    dossier = create_dossier(
                        actor=owner, owner_profile=owner,
                        title=title,
                        description=(
                            "Un résultat concret à préparer et à suivre."
                        ),
                    )
                    profile_stats["dossiers_created"] += 1
                    if sequence % 5 != 4:
                        set_dossier_lifecycle(
                            actor=owner, dossier=dossier, lifecycle="active",
                        )
                else:
                    profile_stats["dossiers_existing"] += 1

                if project is not None:
                    linked = ProjectDossierLink.objects.filter(
                        dossier=dossier, is_active=True,
                    ).first()
                    if linked is None:
                        link_dossier_to_project(
                            actor=owner, project=project, dossier=dossier,
                        )
                        profile_stats["project_links_created"] += 1
                    elif linked.project_id != project.pk:
                        # Do not move an owner-modified Dossier on rerun.
                        profile_stats["existing_parent_preserved"] += 1

                # Some Dossiers are intentionally independent or empty.
                # Other Dossiers have real Journeys and a causal chain.
                links = []
                if journeys and sequence % 5 != 3:
                    for step in range(min(journeys_per_dossier, len(journeys))):
                        journey = journeys[(sequence * 2 + step) % len(journeys)]
                        existing = DossierJourneyLink.objects.filter(
                            dossier=dossier, journey=journey,
                            is_active=True,
                        ).first()
                        link = existing or link_journey(
                            actor=owner, dossier=dossier, journey=journey,
                        )
                        links.append(link)
                        profile_stats[
                            "journey_links_existing" if existing
                            else "journey_links_created"
                        ] += 1

                if len(links) >= 2 and dossier.lifecycle == "active":
                    dependency = DossierJourneyDependency.objects.filter(
                        dossier=dossier, dependent_link=links[1],
                        required_link=links[0],
                    ).exists()
                    if not dependency:
                        add_dependency(
                            actor=owner, dossier=dossier,
                            dependent_link=links[1],
                            required_link=links[0],
                        )
                        profile_stats["dependencies_created"] += 1
                sequence += 1
    return profile_stats


def _sqlite_busy(exc):
    """Retry only the known SQLite contention error, never arbitrary failures."""
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def generate(users, *, count, projects_per_profile=4,
             dossiers_per_project=3, independent_dossiers=2,
             journeys_per_dossier=2, apply=False):
    """Expand Objectives on demo owners with preview and idempotent writes.

    --count bounds the number of owners (not the number of Dossiers).
    Existing Objectives are reused by owner/title. An already linked Dossier
    is never silently moved, and Journey data is never overwritten.
    """
    stats = Counter()
    for owner in users[:min(count, len(users))]:
        # The shared selector allows a named profile outside world_* for
        # other domains. Objectives writes are intentionally more restrictive:
        # a named ordinary user is never a synthetic demo target.
        metadata = getattr(owner, "metadata", None)
        synthetic = owner.username.startswith("world_") or (
            isinstance(metadata, dict)
            and metadata.get("seed") in {
                "mobile-mature-universe",
                "makolo-world-2025-2026-v1",
                "makolo-demo-2024-2027",
            }
        )
        if not synthetic:
            raise ValueError(
                f"Refus Objectives : {owner.username} n'est pas un Profil de démonstration reconnu."
            )
        profile_plan = list(planned_titles(
            owner, projects_per_profile, dossiers_per_project,
            independent_dossiers,
        ))
        journeys = _visible_demo_journeys(owner)
        stats["profiles_selected"] += 1
        stats["eligible_journeys"] += len(journeys)

        if not apply:
            for project_title, dossier_titles in profile_plan:
                project = (
                    _find_project(owner, project_title)
                    if project_title else None
                )
                if project_title:
                    stats["projects_existing" if project else "projects_planned"] += 1
                for title in dossier_titles:
                    dossier = _find_dossier(owner, title)
                    stats["dossiers_existing" if dossier else "dossiers_planned"] += 1
                    if project_title and (
                        dossier is None or not ProjectDossierLink.objects.filter(
                            dossier=dossier, project=project, is_active=True,
                        ).exists()
                    ):
                        stats["project_links_planned"] += 1
            continue

        # Concurrent Django runservers, database viewers or other scripts can
        # hold SQLite locks. A long read-then-write transaction cannot always
        # recover from a changed snapshot by waiting. Roll it back and replay
        # from the beginning, with fresh connections and bounded backoff.
        for attempt in range(3):
            try:
                profile_stats = _apply_one_profile(
                    owner, profile_plan, journeys, journeys_per_dossier,
                )
            except OperationalError as exc:
                if connection.vendor != "sqlite" or not _sqlite_busy(exc):
                    raise
                if attempt == 2:
                    raise RuntimeError(
                        "La base SQLite de démonstration est toujours occupée. "
                        "Arrêtez les serveurs/processus qui utilisent le même "
                        "fichier SQLite, fermez les outils qui gardent une "
                        "transaction ouverte, puis relancez cette commande. "
                        "Aucune écriture partielle de ce Profil n'a été validée."
                    ) from exc
                connections.close_all()
                sleep(0.4 * (attempt + 1))
            except (ValidationError, PermissionDenied):
                stats["profiles_rejected"] += 1
                break
            else:
                stats.update(profile_stats)
                break
    return stats
