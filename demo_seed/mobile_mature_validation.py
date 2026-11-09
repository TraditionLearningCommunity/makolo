from __future__ import annotations

from activities.models import Activity, Occurrence
from events.models import Event
from funding.models import FundingDetails
from journeys.models import Journey
from objectives.models import (
    Dossier, DossierJourneyDependency, DossierJourneyDependencyState,
    DossierJourneyLink, Project, ProjectDossierLink,
)
from objectives.organizer import build_organizer_page
from accounts.models import User
from .common import stable_uuid
from .mobile_objectives import PROJECT_SPECS, INDEPENDENT_DOSSIERS
from obtention.models import ObtentionDetails
from opportunities.models import OpportunityRevision, OpportunitySource, OpportunitySourceType
from preparation.models import ActivityResource, ResourceKind
from services.models import ServiceDetails
from transport.models import TransportService

from .mobile_mature_universe import MOBILE_MATURE_PERSONAS, SEED_MARKER


class MobileMatureDemoValidationError(RuntimeError):
    pass


def assert_mobile_mature_demo_coverage() -> dict[str, int]:
    activities = Activity.objects.filter(slug__startswith="mobile-mature-")
    activity_ids = activities.values_list("pk", flat=True)
    opportunities = OpportunitySource.objects.filter(external_reference__startswith="mobile-mature:")
    profile_email = MOBILE_MATURE_PERSONAS["primary"]

    owner = User.objects.get(email=profile_email)
    project_ids = [
        stable_uuid(f"objectives.project:mobile-mature-{index}")
        for index in range(len(PROJECT_SPECS))
    ]
    dossier_count = sum(len(titles) for _, titles in PROJECT_SPECS) + len(INDEPENDENT_DOSSIERS)
    dossier_ids = [
        stable_uuid(f"objectives.dossier:mobile-mature-{index}")
        for index in range(dossier_count)
    ]
    seeded_projects = Project.objects.filter(pk__in=project_ids, owner_profile=owner)
    seeded_dossiers = Dossier.objects.filter(pk__in=dossier_ids, owner_profile=owner)
    active_project_links = ProjectDossierLink.objects.filter(
        project_id__in=project_ids, dossier_id__in=dossier_ids, is_active=True,
    )
    active_journey_links = DossierJourneyLink.objects.filter(
        dossier_id__in=dossier_ids,
        journey__beneficiary=owner,
        journey__activity__slug__startswith="mobile-mature-",
        is_active=True,
    )
    active_dependencies = DossierJourneyDependency.objects.filter(
        dossier_id__in=dossier_ids,
        state=DossierJourneyDependencyState.ACTIVE,
    )
    counts = {
        "mobile_mature_projects": seeded_projects.count(),
        "mobile_mature_dossiers": seeded_dossiers.count(),
        "mobile_mature_project_dossier_links": active_project_links.count(),
        "mobile_mature_dossier_journey_links": active_journey_links.count(),
        "mobile_mature_dossier_dependencies": active_dependencies.count(),
        "mobile_mature_activities": activities.count(),
        "mobile_mature_events": Event.objects.filter(metadata__seed=SEED_MARKER).count(),
        "mobile_mature_transport": TransportService.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_services": ServiceDetails.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_opportunities": opportunities.values("opportunity_id").distinct().count(),
        "mobile_mature_funding": FundingDetails.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_obtention": ObtentionDetails.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_occurrences": Occurrence.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_resources": ActivityResource.objects.filter(activity_id__in=activity_ids).count(),
        "mobile_mature_file_resources": ActivityResource.objects.filter(activity_id__in=activity_ids, kind=ResourceKind.FILE).count(),
        "mobile_mature_journeys": Journey.objects.filter(beneficiary__email=profile_email, activity_id__in=activity_ids).count(),
        "mobile_mature_2025_occurrences": Occurrence.objects.filter(activity_id__in=activity_ids, start_date__year=2025).count(),
        "mobile_mature_2026_occurrences": Occurrence.objects.filter(activity_id__in=activity_ids, start_date__year=2026).count(),
        "mobile_mature_2027_occurrences": Occurrence.objects.filter(activity_id__in=activity_ids, start_date__year=2027).count(),
    }

    expected = {
        "mobile_mature_activities": 125,
        "mobile_mature_events": 25,
        "mobile_mature_transport": 25,
        "mobile_mature_services": 25,
        "mobile_mature_opportunities": 25,
        "mobile_mature_funding": 25,
        "mobile_mature_obtention": 25,
        "mobile_mature_occurrences": 125,
    }
    for key, value in expected.items():
        if counts[key] != value:
            raise MobileMatureDemoValidationError(f"{key}: attendu {value}, obtenu {counts[key]}.")
    if counts["mobile_mature_resources"] < 150:
        raise MobileMatureDemoValidationError("Le seed mature doit exposer au moins 150 Resources contextuelles.")
    if counts["mobile_mature_file_resources"] < 50:
        raise MobileMatureDemoValidationError("Le seed mature doit contenir un corpus média/fichier significatif.")
    if activities.filter(title__startswith="Exemple — ").exists() or activities.filter(title__startswith="[DEMO]").exists():
        raise MobileMatureDemoValidationError("Une Activity de démonstration expose un marqueur technique dans son titre.")
    synthetic_sources = OpportunitySource.objects.filter(external_reference__startswith="mobile-mature:")
    if synthetic_sources.exclude(source_type=OpportunitySourceType.USER_SUPPLIED).exists() or synthetic_sources.filter(verified_at__isnull=False).exists():
        raise MobileMatureDemoValidationError("Une référence de démonstration ne doit pas certifier une offre fictive.")
    synthetic_revisions = OpportunityRevision.objects.filter(opportunity__sources__external_reference__startswith="mobile-mature:")
    if synthetic_revisions.filter(title__startswith="Exemple — ").exists() or synthetic_revisions.filter(title__startswith="[DEMO]").exists():
        raise MobileMatureDemoValidationError("Une candidature de démonstration expose un marqueur technique dans son titre.")
    if counts["mobile_mature_journeys"] < 30:
        raise MobileMatureDemoValidationError("Le persona principal doit posséder un historique/présent riche de Journeys.")
    if counts["mobile_mature_projects"] != len(PROJECT_SPECS):
        raise MobileMatureDemoValidationError("Le profil mobile doit avoir 6 Projets canoniques.")
    if counts["mobile_mature_dossiers"] != dossier_count:
        raise MobileMatureDemoValidationError("Les Dossiers mobiles de démonstration sont incomplets.")
    if counts["mobile_mature_project_dossier_links"] != dossier_count - len(INDEPENDENT_DOSSIERS):
        raise MobileMatureDemoValidationError("Les liens Projet-Dossier sont incomplets.")
    if counts["mobile_mature_dossier_journey_links"] < 40:
        raise MobileMatureDemoValidationError("Trop peu de démarches réellement liées aux Dossiers.")
    if counts["mobile_mature_dossier_dependencies"] < 5:
        raise MobileMatureDemoValidationError("Les prérequis canoniques des Dossiers sont incomplets.")

    # Assert the actual Flutter collection, not only database table counts.
    page = build_organizer_page(owner, limit=50)
    items = page["items"]
    visible_project_ids = {row["id"] for row in items if row["kind"] == "project"}
    visible_dossier_ids = {row["id"] for row in items if row["kind"] == "dossier"}
    if not set(map(str, project_ids)).issubset(visible_project_ids):
        raise MobileMatureDemoValidationError("Les Projets ne remontent pas dans Mes démarches.")
    if not set(map(str, dossier_ids)).issubset(visible_dossier_ids):
        raise MobileMatureDemoValidationError("Les Dossiers ne remontent pas dans Mes démarches.")
    if not any(row.get("project_id") for row in items if row["kind"] == "dossier"):
        raise MobileMatureDemoValidationError("Le lien parent Projet-Dossier n'est pas projeté.")
    if not any(row.get("dossier_ids") for row in items if row["kind"] == "journey"):
        raise MobileMatureDemoValidationError("Les parents Dossier-Journey ne sont pas projetés.")
    counts["mobile_mature_organizer_visible_items"] = len(items)

    for year in (2025, 2026, 2027):
        if counts[f"mobile_mature_{year}_occurrences"] <= 0:
            raise MobileMatureDemoValidationError(f"Aucune Occurrence mobile mature en {year}.")
    return counts
