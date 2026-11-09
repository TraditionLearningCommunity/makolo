"""Rebalance demo visibility across synthetic profiles and Spaces.

This only adds missing, bounded bookmarks/follows through existing domain paths.
It does NOT transfer Activity/Space ownership, grant Mandates or rewrite Journey
or payment histories. Re-running with the same target is idempotent.
"""
import argparse
from collections import Counter
from hashlib import sha256


TARGETS = ("profiles", "spaces")


def rank_items(profile, items, seed):
    """Stable rotation, independent of database row order."""
    return sorted(
        items,
        key=lambda item: sha256(
            f"{seed}:{profile.pk}:{item.pk}".encode("utf-8")
        ).digest(),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--profiles", type=int, default=30)
    parser.add_argument("--profile-username")
    parser.add_argument("--space-id", help="Restrict space follows to one synthetic Space UUID")
    parser.add_argument("--count", type=int, default=50, help="Total new relations at most")
    parser.add_argument("--per-profile", type=int, default=3,
                        help="Desired maximum synthetic relations per profile")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--direction", choices=("add", "trim"), default="add")
    parser.add_argument("--activity-prefix", default="demo-")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", action="store_true", help="Create a SQLite backup before applying")
    args = parser.parse_args(argv)
    if not 1 <= args.profiles <= 100 or not 1 <= args.count <= 5000:
        parser.error("--profiles 1..100; --count 1..5000")
    if not 1 <= args.per_profile <= 30:
        parser.error("--per-profile 1..30")
    if args.profile_username and not args.profile_username.startswith("world_"):
        parser.error("Rebalancing requires a synthetic world_* profile")
    if args.space_id and args.target != "spaces":
        parser.error("--space-id requires --target spaces")
    if not args.activity_prefix.startswith("demo-"):
        parser.error("--activity-prefix must start with demo-")
    if args.target == "spaces" and args.activity_prefix != "demo-":
        parser.error("--activity-prefix is only meaningful for profiles")
    if args.space_id:
        import uuid
        try:
            uuid.UUID(args.space_id)
        except ValueError:
            parser.error("--space-id must be a UUID")

    import django
    django.setup()
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from activities.models import Activity, ActivityStatus, ActivityVisibility
    from discovery.models import ActivityBookmark
    from organizations.models import Organization, OrganizationFollow
    from organizations.services import follow_organization, unfollow_organization
    from .scope import demo_activities, demo_spaces
    from .selection import demo_profiles

    if connection.vendor != "sqlite":
        parser.error("Rebalancing is restricted to the demonstration SQLite")
    if args.backup and args.apply:
        from .scope import backup_demo_sqlite
        print("BACKUP", backup_demo_sqlite(connection))
    people = demo_profiles(username=args.profile_username, limit=args.profiles)
    counters = Counter()
    previews = []
    remaining = args.count

    if args.target == "profiles":
        activities = list(demo_activities(Activity.objects).filter(
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
            slug__startswith=args.activity_prefix,
        ).select_related("space", "owner_profile")[:10000])
        for person in people:
            if args.direction == "trim":
                links = list(ActivityBookmark.objects.filter(
                    user=person, activity__slug__startswith=args.activity_prefix
                ))
                for link in rank_items(person, links, args.seed)[args.per_profile:]:
                    if not remaining:
                        break
                    remaining -= 1
                    counters["bookmarks_trim_planned"] += 1
                    if len(previews) < 8:
                        previews.append(f"{person.username} - bookmark {link.activity_id}")
                    if args.apply:
                        with transaction.atomic():
                            link.delete()
                        counters["bookmarks_removed"] += 1
                if not remaining:
                    break
                continue
            existing = set(ActivityBookmark.objects.filter(
                user=person, activity__slug__startswith=args.activity_prefix
            ).values_list("activity_id", flat=True))
            missing = max(0, args.per_profile - len(existing))
            for activity in rank_items(person, activities, args.seed):
                if not missing or not remaining:
                    break
                # Synthetic demo choices must not point to an owner's own content.
                if activity.pk in existing or (
                    activity.owner_profile_id == person.pk or
                    (activity.space_id and activity.space.created_by_id == person.pk)
                ):
                    continue
                remaining -= 1
                missing -= 1
                counters["bookmarks_planned"] += 1
                if len(previews) < 8:
                    previews.append(f"{person.username} -> {activity.slug}")
                if args.apply:
                    with transaction.atomic():
                        _, created = ActivityBookmark.objects.get_or_create(
                            user=person, activity=activity
                        )
                    counters["bookmarks_created"] += int(created)
            if remaining == 0:
                break
    else:
        # The target profile may be different from the Space creators.
        owners = demo_profiles(limit=100)
        spaces = demo_spaces(Organization.objects.filter(
            public_profile=True
        ).exclude(verification_status="suspended"), owners)
        if args.space_id:
            spaces = spaces.filter(pk=args.space_id)
        choices = list(spaces[:10000])
        for person in people:
            if args.direction == "trim":
                links = list(OrganizationFollow.objects.filter(
                    user=person, organization__in=choices
                ))
                for follow in rank_items(person, links, args.seed)[args.per_profile:]:
                    if not remaining:
                        break
                    remaining -= 1
                    counters["follows_trim_planned"] += 1
                    if len(previews) < 8:
                        previews.append(f"{person.username} - follow {follow.organization_id}")
                    if args.apply:
                        try:
                            with transaction.atomic():
                                unfollow_organization(follow=follow, user=person)
                            counters["follows_removed"] += 1
                        except (ValidationError, PermissionDenied):
                            counters["follows_remove_rejected"] += 1
                if not remaining:
                    break
                continue
            existing = set(OrganizationFollow.objects.filter(
                user=person, organization__in=choices
            ).values_list("organization_id", flat=True))
            missing = max(0, args.per_profile - len(existing))
            for space in rank_items(person, choices, args.seed):
                if not missing or not remaining:
                    break
                if space.pk in existing or space.created_by_id == person.pk:
                    continue
                remaining -= 1
                missing -= 1
                counters["follows_planned"] += 1
                if len(previews) < 8:
                    previews.append(f"{person.username} -> {space.slug}")
                if args.apply:
                    try:
                        with transaction.atomic():
                            follow_organization(
                                user=person, organization=space,
                                notify_new_events=False, notify_announcements=False,
                                email_new_events=False, email_announcements=False,
                            )
                        counters["follows_created"] += 1
                    except (ValidationError, PermissionDenied):
                        counters["follows_rejected"] += 1
            if remaining == 0:
                break

    print("REBALANCE", args.target, args.direction, "APPLY" if args.apply else "PREVIEW")
    print("SUMMARY", dict(sorted(counters.items())))
    for item in previews:
        print("SAMPLE", item)
    print("No ownership transfers, Mandates, external deliveries or historical rewrites.")


if __name__ == "__main__":
    main()
