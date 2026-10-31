"""Scenarios personnels: favoris, veilles Discover, objectifs, suivi d'Espaces.

Toutes les relations partent de profils world_* existants. Les declarations
explicites du profil ne sont jamais derivees du comportement en cachette.
"""
import argparse
from collections import Counter
from datetime import timedelta


DOMAINS = ("discovery", "goals", "space")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default=",".join(DOMAINS))
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    domains = set(a.domains.split(","))
    if not domains or not domains <= set(DOMAINS):
        p.error("Domains: discovery,goals,space")
    if not 1 <= a.count <= 2000 or not 1 <= a.profiles <= 100:
        p.error("count 1..2000; profiles 1..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus, ActivityVisibility
    from discovery.models import ActivityBookmark, DiscoveryWatch
    from discovery.watches import ensure_discovery_watch
    from goals.models import PersonalGoal, PersonalGoalType
    from goals.services import create_personal_goal
    from organizations.models import Organization, OrganizationFollow
    from organizations.services import follow_organization
    if connection.vendor != "sqlite":
        p.error("SQLite demo only")
    users = list(get_user_model().objects.filter(
        username__startswith="world_", is_active=True,
        is_staff=False, is_superuser=False,
    ).order_by("username")[:a.profiles])
    activities = list(Activity.objects.filter(
        slug__startswith="demo-", status=ActivityStatus.PUBLISHED,
        visibility=ActivityVisibility.PUBLIC,
    ).order_by("id")[:max(20, a.count)])
    spaces = list(Organization.objects.filter(
        public_profile=True,
    ).exclude(verification_status="suspended").order_by("id")[:a.count])
    if not users:
        p.error("No synthetic world_* users")
    counts = Counter()
    today = timezone.localdate()
    month_start = today.replace(day=1)
    next_start = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_start - timedelta(days=1)
    for index in range(a.count):
        user = users[index % len(users)]
        if "discovery" in domains:
            if activities:
                activity = activities[index % len(activities)]
                if ActivityBookmark.objects.filter(user=user, activity=activity).exists():
                    counts["bookmark_existing"] += 1
                elif not a.apply:
                    counts["bookmark_planned"] += 1
                else:
                    ActivityBookmark.objects.get_or_create(user=user, activity=activity)
                    counts["bookmark_created"] += 1
            criteria = {"q": "formation" if index % 2 else "atelier"}
            if DiscoveryWatch.objects.filter(owner=user,
                    criteria__q=criteria["q"], status="active").exists():
                counts["watch_existing"] += 1
            elif not a.apply:
                counts["watch_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        watch, created = ensure_discovery_watch(
                            owner=user, criteria=criteria,
                            name="[DEMO] Veille " + criteria["q"])
                    counts["watch_created" if created else "watch_existing"] += 1
                except (ValidationError, PermissionDenied):
                    counts["watch_rejected"] += 1
        if "goals" in domains:
            exists = PersonalGoal.objects.filter(
                profile=user, goal_type=PersonalGoalType.JOURNEYS_COMPLETED,
                period_start=month_start, period_end=month_end,
            ).exists()
            if exists:
                counts["goal_existing"] += 1
            elif not a.apply:
                counts["goal_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        create_personal_goal(
                            profile=user, goal_type=PersonalGoalType.JOURNEYS_COMPLETED,
                            target_value=2 + (index % 4),
                            period_start=month_start, period_end=month_end)
                    counts["goal_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["goal_rejected"] += 1
        if "space" in domains and spaces:
            space = spaces[index % len(spaces)]
            if OrganizationFollow.objects.filter(user=user, organization=space).exists():
                counts["space_follow_existing"] += 1
            elif not a.apply:
                counts["space_follow_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        follow_organization(user=user, organization=space,
                            notify_new_events=True, notify_announcements=True,
                            email_new_events=False, email_announcements=False)
                    counts["space_follow_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["space_follow_rejected"] += 1
    print("PERSONAL", "APPLY" if a.apply else "PREVIEW",
          dict(sorted(counts.items())))
    print("Bookmarks and Watches are personal choices made by synthetic demo profiles.")


if __name__ == "__main__":
    main()
