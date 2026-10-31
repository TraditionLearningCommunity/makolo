"""Additional Jour J operations: placement zones and synthetic incidents.

No Capacity is represented by Placement. Assignments use the canonical
placement service. Incident authority is verified by the production service.
"""
import argparse
from collections import Counter


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--actor", default="beta_event_manager")
    p.add_argument("--domains", default="placement,incidents")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= {"placement", "incidents"}:
        p.error("Domains: placement,incidents")
    if not 1 <= a.count <= 200:
        p.error("count 1..200")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Occurrence, ActivityStatus, OccurrenceStatus
    from journeys.models import Journey
    from operations.permissions import user_can_manage_activity_operations
    from operations.placement_models import PlacementPlan, PlacementUnit, PlacementAssignment
    from operations.placement_services import assign_placement
    from operations.models import OperationsIncident, IncidentCategory, IncidentSeverity
    from operations.incident_services import create_incident
    if connection.vendor != "sqlite":
        p.error("SQLite demo only")
    operator = get_user_model().objects.filter(
        username=a.actor, is_active=True, is_staff=False, is_superuser=False
    ).first()
    if not operator:
        p.error("Demo non-admin operator is unavailable")
    now = timezone.now()
    live = Occurrence.objects.select_related("activity", "activity__space").filter(
        activity__slug__startswith="demo-", activity__status=ActivityStatus.PUBLISHED,
        start_at__lte=now, end_at__gt=now
    ).exclude(status__in=[OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED]).order_by(
        "start_at", "id"
    )[:max(100, a.count * 5)]
    counts = Counter()
    covered = 0
    for occurrence in live:
        if covered >= a.count:
            break
        if not user_can_manage_activity_operations(operator, occurrence.activity):
            counts["no_authority"] += 1
            continue
        journeys = list(Journey.objects.filter(
            activity=occurrence.activity, occurrence=occurrence,
            beneficiary__username__startswith="world_"
        ).exclude(status__in=["rejected", "cancelled", "expired"]).select_related(
            "beneficiary").order_by("id")[:8])
        if not journeys:
            counts["no_journey"] += 1
            continue
        covered += 1
        plan = PlacementPlan.objects.filter(
            occurrence=occurrence, key="demo-zones"
        ).first()
        if not a.apply:
            if "placement" in selected:
                counts["placement_planned"] += int(plan is None)
                counts["assignments_planned"] += len({j.beneficiary_id for j in journeys})
            if "incidents" in selected:
                counts["incidents_planned"] += int(not OperationsIncident.objects.filter(
                    occurrence=occurrence, title="[DEMO] Controle de circulation").exists())
            continue
        if "placement" in selected:
            try:
                with transaction.atomic():
                    if plan is None:
                        plan = PlacementPlan.objects.create(
                            occurrence=occurrence, key="demo-zones",
                            label="Zones de demonstration", required=False, active=True)
                        counts["placement_plans_created"] += 1
                    units = []
                    for key in ("zone-a", "zone-b"):
                        unit, created = PlacementUnit.objects.get_or_create(
                            plan=plan, key=key,
                            defaults={"label":"Zone "+key[-1].upper(), "kind":"zone",
                                      "exclusive":False, "active":True})
                        units.append(unit)
                        counts["units_created"] += int(created)
                    for index, journey in enumerate(journeys):
                        if PlacementAssignment.objects.filter(
                            plan=plan, profile=journey.beneficiary,
                            ended_at__isnull=True).exists():
                            counts["assignments_existing"] += 1
                            continue
                        assign_placement(actor=operator, plan=plan,
                            unit=units[index % len(units)], profile=journey.beneficiary)
                        counts["assignments_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["placement_rejected"] += 1
        if "incidents" not in selected:
            continue
        title = "[DEMO] Controle de circulation"
        if OperationsIncident.objects.filter(
            occurrence=occurrence, title=title
        ).exists():
            counts["incidents_existing"] += 1
            continue
        try:
            with transaction.atomic():
                create_incident(actor=operator, title=title,
                    category=IncidentCategory.OTHER,
                    severity=IncidentSeverity.LOW,
                    description="Incident purement fictif pour verifier le triage operationnel.",
                    activity=occurrence.activity, occurrence=occurrence,
                    organization=occurrence.activity.space,
                    metadata={"synthetic_demo":True})
            counts["incidents_created"] += 1
        except (ValidationError, PermissionDenied):
            counts["incidents_no_authority_or_invalid"] += 1
    print("LIVE DETAIL", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
