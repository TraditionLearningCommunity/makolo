"""Espace, programmes de fidélité et politiques Automation synthétiques.

Construire des Espaces possédés par des world_* puis composer les services
canoniques. Les politiques Automation ne simulent pas des envois externes.
"""
import argparse
from collections import Counter
from datetime import timedelta


DOMAINS = ("spaces", "loyalty", "automation")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default=",".join(DOMAINS))
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    chosen = set(a.domains.split(","))
    if not chosen or not chosen <= set(DOMAINS):
        p.error("Domains: spaces,loyalty,automation")
    if not 1 <= a.count <= 100 or not 2 <= a.profiles <= 100:
        p.error("count 1..100 and profiles 2..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
    from activities.services import create_activity, create_occurrence, complete_occurrence
    from organizations.models import Organization, TeamMembership
    from organizations.services import create_organization, add_or_update_member
    from loyalty.models import LoyaltyProgram, LoyaltyTier, MembershipPlan, MembershipSubscription
    from loyalty.services import request_membership
    from automation.models import EventAutomationPolicy
    from automation.services import ensure_policy
    from events.models import Event
    if connection.vendor != "sqlite":
        p.error("SQLite demonstration required")
    people = list(get_user_model().objects.filter(
        username__startswith="world_", is_active=True,
        is_staff=False, is_superuser=False,
    ).order_by("username")[:a.profiles])
    if len(people) < 2:
        p.error("At least two world_* users required")
    now = timezone.now()
    counts = Counter()
    # Space creation precedes loyalty: composition, no duplicated ownership.
    if "spaces" in chosen:
        for i in range(min(a.count, len(people))):
            owner = people[i]
            name = "[DEMO] Espace " + owner.username
            org = Organization.objects.filter(created_by=owner, name=name).first()
            if org is None and not a.apply:
                counts["spaces_planned"] += 1
                continue
            if org is None:
                try:
                    with transaction.atomic():
                        org = create_organization(creator=owner, name=name,
                            description="Espace fictif pour les tests multi-acteurs.",
                            public_profile=True, searchable=True)
                    counts["spaces_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["spaces_rejected"] += 1
                    continue
            else:
                counts["spaces_existing"] += 1
            member = people[(i + 1) % len(people)]
            if not TeamMembership.objects.filter(team__organization=org,
                    user=member, status="active").exists():
                if not a.apply:
                    counts["members_planned"] += 1
                else:
                    try:
                        with transaction.atomic():
                            add_or_update_member(
                                organization=org, actor=owner,
                                user=member, role="space-admin")
                        counts["members_created"] += 1
                    except (PermissionDenied, ValidationError):
                        counts["members_rejected"] += 1
            slug = "demo-space-activity-" + owner.username.lower().replace("_", "-")
            activity = Activity.objects.filter(space=org, slug=slug).first()
            if activity is None and not a.apply:
                counts["space_activities_planned"] += 1
                continue
            if activity is None:
                try:
                    with transaction.atomic():
                        activity = create_activity(
                            created_by=owner, space=org,
                            title="[DEMO] Atelier collectif de " + owner.username,
                            short_description="Activité organisée au nom d'un Espace fictif.",
                            status=ActivityStatus.PUBLISHED)
                        activity.slug = slug
                        activity.full_clean()
                        activity.save(update_fields=["slug", "updated_at"])
                    counts["space_activities_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["space_activities_rejected"] += 1
                    continue
            windows = (
                ("historique", now-timedelta(days=7), timedelta(hours=3),
                 OccurrenceStatus.COMPLETED),
                ("en-cours", now-timedelta(minutes=25), timedelta(hours=3),
                 OccurrenceStatus.SCHEDULED),
                ("demain", now+timedelta(days=1), timedelta(hours=3),
                 OccurrenceStatus.SCHEDULED),
            )
            for label, start, duration, state in windows:
                if Occurrence.objects.filter(activity=activity, label="DEMO " + label).exists():
                    counts["occurrences_existing"] += 1
                    continue
                if not a.apply:
                    counts["occurrences_planned"] += 1
                    continue
                try:
                    with transaction.atomic():
                        occurrence = create_occurrence(
                            activity=activity, timezone="Africa/Lubumbashi",
                            label="DEMO " + label, start_at=start,
                            end_at=start+duration, status=OccurrenceStatus.SCHEDULED)
                        if state == OccurrenceStatus.COMPLETED:
                            complete_occurrence(occurrence=occurrence)
                            counts["occurrences_completed"] += 1
                    counts["occurrences_created"] += 1
                except ValidationError:
                    counts["occurrences_rejected"] += 1

    if "loyalty" in chosen:
        spaces = Organization.objects.filter(name__startswith="[DEMO] Espace ").select_related(
            "created_by").order_by("id")[:a.count]
        for org in spaces:
            owner = org.created_by
            if owner is None or not owner.is_active:
                counts["loyalty_no_owner"] += 1
                continue
            program = LoyaltyProgram.objects.filter(organization=org).first()
            if not a.apply:
                counts["loyalty_planned"] += int(program is None)
                continue
            try:
                with transaction.atomic():
                    if program is None:
                        program = LoyaltyProgram(
                            organization=org, name="Fidélité [DEMO]",
                            description="Programme fictif lié à un Espace fictif.",
                            created_by=owner, points_per_order=10,
                            points_per_ticket=5, points_per_checkin=20)
                        program.full_clean()
                        program.save()
                        counts["loyalty_programs_created"] += 1
                    for code, threshold in (("START",0),("ACTIVE",150)):
                        tier, created = LoyaltyTier.objects.get_or_create(
                            program=program, code=code,
                            defaults={"name":"Niveau "+code,
                                      "threshold_points":threshold})
                        counts["loyalty_tiers_created"] += int(created)
                    plan, created = MembershipPlan.objects.get_or_create(
                        program=program, code="DEMO-FREE",
                        defaults={"name":"Adhésion fictive gratuite",
                                  "price":0, "currency":"USD",
                                  "duration_days":365, "created_by":owner})
                    counts["membership_plans_created"] += int(created)
                    for person in people[:min(a.profiles, 10)]:
                        already = MembershipSubscription.objects.filter(
                            user=person, program=program, status__in=("pending","active")
                        ).exists()
                        request_membership(user=person, plan=plan)
                        counts["memberships_created"] += int(not already)
            except (ValidationError, PermissionDenied):
                counts["loyalty_rejected"] += 1

    if "automation" in chosen:
        events = Event.objects.filter(
            activity__slug__startswith="demo-",
            activity__status=ActivityStatus.PUBLISHED,
        ).order_by("id")[:max(a.count*5, 20)]
        for event in events:
            if counts["automation_considered"] >= a.count:
                break
            counts["automation_considered"] += 1
            if EventAutomationPolicy.objects.filter(event=event).exists():
                counts["automation_existing"] += 1
            elif not a.apply:
                counts["automation_planned"] += 1
            else:
                ensure_policy(event)
                counts["automation_policies_created"] += 1

    print("ECOSYSTEM", "APPLY" if a.apply else "PREVIEW",
          dict(sorted(counts.items())))
    print("No external sends; Automation runs remain owned by the engine.")


if __name__ == "__main__":
    main()
