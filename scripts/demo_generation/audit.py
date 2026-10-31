"""Read-only readiness audit for the demonstration at a reference instant."""
import argparse
from datetime import datetime
from collections import OrderedDict


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--at", help="ISO-8601 timestamp with offset, e.g. 2026-10-30T18:00:00+02:00")
    a = p.parse_args(argv)
    import django
    django.setup()
    from django.utils import timezone
    from django.db import connection
    from django.apps import apps
    from django.db.models import Q
    from activities.models import Activity, Occurrence, ActivityStatus, OccurrenceStatus
    from journeys.models import Journey
    from access.models import Access, AccessUse
    from scanner.models import ScanLog, ScannerAssignment
    from operations.checkpoint_models import OccurrenceCheckpoint
    from operations.queue_models import OccurrenceQueue, QueueEntry
    from operations.placement_models import PlacementPlan, PlacementAssignment
    from operations.models import OperationsIncident
    from presentations.models import PresentationAsset, PresentationMediaUse
    from events.models import Event
    from funding.models import FundingDetails, FundingContribution
    from services.models import ServiceDetails, ServiceJourneyContext
    from obtention.models import ObtentionDetails, ObtentionJourneyContext
    from opportunities.models import Opportunity, OpportunitySave
    from groups.models import Group, GroupMembership
    from objectives.models import Dossier, Project
    from trust.models import Feedback
    from notifications.models import Notification
    from crm.models import CRMContact
    from questionnaires.models import Form, FormRequest
    from social.models import Contribution
    if connection.vendor != "sqlite":
        p.error("Readiness audit only on a SQLite demonstration database")
    if a.at:
        try:
            instant = datetime.fromisoformat(a.at.replace("Z", "+00:00"))
            if timezone.is_naive(instant):
                p.error("--at must include a timezone offset")
        except ValueError:
            p.error("--at must be an ISO-8601 datetime")
    else:
        instant = timezone.now()

    demo_activities = Activity.objects.filter(slug__startswith="demo-")
    live_occurrences = Occurrence.objects.filter(
        activity__slug__startswith="demo-", activity__status=ActivityStatus.PUBLISHED,
        start_at__lte=instant, end_at__gt=instant
    ).exclude(status__in=[OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED])
    future = Occurrence.objects.filter(
        activity__slug__startswith="demo-", start_at__gt=instant
    ).exclude(status=OccurrenceStatus.CANCELLED)
    demos = dict(
        activities=demo_activities.count(),
        occurrences_live=live_occurrences.count(),
        occurrences_future=future.count(),
        journey=Journey.objects.filter(activity__slug__startswith="demo-").count(),
        access=Access.objects.filter(activity__slug__startswith="demo-").count(),
        access_use=AccessUse.objects.filter(access__activity__slug__startswith="demo-").count(),
        checkpoint_live=OccurrenceCheckpoint.objects.filter(
            occurrence__in=live_occurrences, active=True, status="open").count(),
        queue_live=OccurrenceQueue.objects.filter(occurrence__in=live_occurrences, status="open").count(),
        queue_entries=QueueEntry.objects.filter(queue__occurrence__in=live_occurrences).count(),
        placement_plans=PlacementPlan.objects.filter(occurrence__in=live_occurrences).count(),
        placements=PlacementAssignment.objects.filter(plan__occurrence__in=live_occurrences, ended_at__isnull=True).count(),
        incidents=OperationsIncident.objects.filter(activity__slug__startswith="demo-").count(),
        event=Event.objects.filter(activity__slug__startswith="demo-").count(),
        scan_log=ScanLog.objects.filter(event__activity__slug__startswith="demo-").count(),
        scanner_assignment=ScannerAssignment.objects.filter(
            activity__slug__startswith="demo-", is_active=True).count(),
        media_assets=PresentationAsset.objects.count(),
        media_published=PresentationMediaUse.objects.filter(
            activity__slug__startswith="demo-", state="published").count(),
        funding=FundingDetails.objects.filter(activity__slug__startswith="demo-").count(),
        funding_contribution=FundingContribution.objects.filter(
            funding__activity__slug__startswith="demo-").count(),
        services=ServiceDetails.objects.filter(activity__slug__startswith="demo-").count(),
        service_journeys=ServiceJourneyContext.objects.filter(
            journey__activity__slug__startswith="demo-").count(),
        obtention=ObtentionDetails.objects.filter(activity__slug__startswith="demo-").count(),
        obtention_journeys=ObtentionJourneyContext.objects.filter(
            journey__activity__slug__startswith="demo-").count(),
        opportunities=Opportunity.objects.filter(publication_status="published").count(),
        opportunity_saves=OpportunitySave.objects.count(),
        groups=Group.objects.filter(name__startswith="[DEMO]").count(),
        members=GroupMembership.objects.filter(group__name__startswith="[DEMO]").count(),
        dossiers=Dossier.objects.filter(title__startswith="[DEMO]").count(),
        projects=Project.objects.filter(title__startswith="[DEMO]").count(),
        feedback=Feedback.objects.filter(journey__activity__slug__startswith="demo-").count(),
        notifications=Notification.objects.filter(dedup_key__startswith="demo-generation:").count(),
        crm_contacts=CRMContact.objects.count(),
        forms=Form.objects.filter(activity__slug__startswith="demo-").count(),
        form_requests=FormRequest.objects.filter(journey__activity__slug__startswith="demo-").count(),
        contributions=Contribution.objects.filter(activity__slug__startswith="demo-").count(),
    )
    model_for_key = {
        "activities":"activities.Activity",
        "journey":"journeys.Journey", "access":"access.Access",
        "access_use":"access.AccessUse",
        "event":"events.Event", "scan_log":"scanner.ScanLog",
        "scanner_assignment":"scanner.ScannerAssignment",
        "media_assets":"presentations.PresentationAsset",
        "media_published":"presentations.PresentationMediaUse",
        "funding":"funding.FundingDetails",
        "funding_contribution":"funding.FundingContribution",
        "services":"services.ServiceDetails",
        "service_journeys":"services.ServiceJourneyContext",
        "obtention":"obtention.ObtentionDetails",
        "obtention_journeys":"obtention.ObtentionJourneyContext",
        "opportunities":"opportunities.Opportunity",
        "opportunity_saves":"opportunities.OpportunitySave",
        "groups":"groups.Group", "members":"groups.GroupMembership",
        "dossiers":"objectives.Dossier","projects":"objectives.Project",
        "feedback":"trust.Feedback",
        "notifications":"notifications.Notification",
        "crm_contacts":"crm.CRMContact",
        "forms":"questionnaires.Form","form_requests":"questionnaires.FormRequest",
        "contributions":"social.Contribution",
        "placement_plans":"operations.PlacementPlan",
        "placements":"operations.PlacementAssignment",
        "incidents":"operations.OperationsIncident",
        "checkpoint_live":"operations.OccurrenceCheckpoint",
        "queue_live":"operations.OccurrenceQueue",
        "queue_entries":"operations.QueueEntry",
    }
    totals = {key:apps.get_model(label).objects.count()
              for key,label in model_for_key.items()}
    totals["occurrences_live"] = Occurrence.objects.filter(
        activity__status=ActivityStatus.PUBLISHED,
        start_at__lte=instant,end_at__gt=instant,
    ).exclude(status__in=[OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED]).count()
    totals["occurrences_future"] = Occurrence.objects.filter(
        start_at__gt=instant).exclude(status=OccurrenceStatus.CANCELLED).count()
    print("AUDIT AT", instant.isoformat())
    print("COUNTS: demo-scope | entire SQLite (where applicable)")
    for key, count in demos.items():
        total = totals.get(key)
        if total is None:
            print(f"{key:27s} {count}")
        else:
            print(f"{key:27s} {count:8d} | {total:8d}")
    essential = {
        "Jour J / Live": ("occurrences_live", "checkpoint_live", "queue_live", "queue_entries"),
        "Placement / Incidents": ("placement_plans", "placements", "incidents"),
        "Access / Scanner": ("access", "access_use", "scanner_assignment", "scan_log"),
        "Images": ("media_assets", "media_published"),
        "Funding": ("funding", "funding_contribution"),
        "Services": ("services", "service_journeys"),
        "Obtention": ("obtention", "obtention_journeys"),
        "Relations": ("groups", "dossiers", "projects"),
        "Forms / CRM": ("forms", "form_requests", "crm_contacts"),
        "Contextual content": ("contributions", "media_published"),
    }
    for title, keys in essential.items():
        missing = [key for key in keys if demos[key] == 0]
        outside = [key for key in missing if totals.get(key, 0) > 0]
        absent = [key for key in missing if totals.get(key, 0) == 0]
        if missing:
            print("READINESS", title, "MISSING_DEMO:", ",".join(missing))
            if outside:
                print("  EXISTS_OUTSIDE_DEMO:", ",".join(outside))
            if absent:
                print("  EMPTY_GLOBALLY:", ",".join(absent))
        else:
            print("READINESS", title, "HAS_DEMO_DATA")
    print("Scopes are distinct: a real existing Service/Funding/Obtention row is not automatically a demo row.")
    print("HAS_DEMO_DATA does not certify functional tests or eligibility.")
    print("No changes were made.")


if __name__ == "__main__":
    main()
