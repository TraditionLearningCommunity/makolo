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
    from django.db.models import Q
    from activities.models import Activity, Occurrence, ActivityStatus, OccurrenceStatus
    from journeys.models import Journey
    from access.models import Access, AccessUse
    from scanner.models import ScanLog, ScannerAssignment
    from operations.checkpoint_models import OccurrenceCheckpoint
    from operations.queue_models import OccurrenceQueue, QueueEntry
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
    )
    print("AUDIT AT", instant.isoformat())
    for key, count in demos.items():
        print(f"{key:27s} {count}")
    essential = {
        "Jour J / Live": ("occurrences_live", "checkpoint_live", "queue_live", "queue_entries"),
        "Access / Scanner": ("access", "access_use", "scanner_assignment", "scan_log"),
        "Images": ("media_assets", "media_published"),
        "Funding": ("funding", "funding_contribution"),
        "Services": ("services", "service_journeys"),
        "Obtention": ("obtention", "obtention_journeys"),
        "Relations": ("groups", "dossiers", "projects"),
    }
    for title, keys in essential.items():
        missing = [key for key in keys if demos[key] == 0]
        print("READINESS", title, "INCOMPLETE:" + ",".join(missing) if missing else "HAS_DATA")
    print("HAS_DATA does not certify functional test coverage or eligibility.")
    print("No changes were made.")


if __name__ == "__main__":
    main()
