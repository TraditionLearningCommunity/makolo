from __future__ import annotations

from activities.models import Activity, Occurrence
from events.models import Event
from funding.models import FundingDetails
from journeys.models import Journey
from obtention.models import ObtentionDetails
from opportunities.models import OpportunitySource
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

    counts = {
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
    if counts["mobile_mature_journeys"] < 30:
        raise MobileMatureDemoValidationError("Le persona principal doit posséder un historique/présent riche de Journeys.")
    for year in (2025, 2026, 2027):
        if counts[f"mobile_mature_{year}_occurrences"] <= 0:
            raise MobileMatureDemoValidationError(f"Aucune Occurrence mobile mature en {year}.")
    return counts
