"""Selective, manually triggered maintenance of synthetic demo scenarios.

complete delegates to the existing generator orchestration. refresh updates
only synthetic Activity editorial text. retire/restore use reversible Activity
status changes; nothing is deleted or silently reassigned.
"""
import argparse
from collections import Counter
from datetime import timedelta


ACTIONS = ("complete", "refresh", "retire", "restore")
DESCRIPTIONS = (
    "Retrouvez les informations pratiques et les prochaines étapes de cette activité.",
    "Consultez les modalités et organisez votre participation à cette activité.",
    "Explorez ce parcours et les informations utiles pour préparer votre démarche.",
    "Découvrez cette initiative et les possibilités de participation présentées ici.",
)


def editorial_text(edition, identifier):
    """Reproducible copy variation, never a claim about external reality."""
    from hashlib import sha256
    digest = sha256(f"{edition}:{identifier}".encode("utf-8")).digest()
    return DESCRIPTIONS[int.from_bytes(digest[:4], "big") % len(DESCRIPTIONS)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--domains", default="all", help="Existing generation domains for complete")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--profiles", type=int, default=30)
    parser.add_argument("--profile-username")
    parser.add_argument("--space-id", help="Filter a synthetic Activity's owning Space UUID")
    parser.add_argument("--activity-prefix", default="demo-")
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--edition", type=int, default=1,
                        help="Stable editorial variant (repeat = no extra changes)")
    parser.add_argument("--grant-roles", action="store_true",
                        help="Explicit opt-in for the canonical Mandates generator")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", action="store_true", help="Create a SQLite backup before applying")
    args = parser.parse_args(argv)

    if not 1 <= args.count <= 100000 or not 1 <= args.profiles <= 100:
        parser.error("--count 1..100000; --profiles 1..100")
    if not 0 <= args.older_than_days <= 36500 or not 0 <= args.edition <= 100000:
        parser.error("--older-than-days 0..36500; --edition 0..100000")
    if not args.activity_prefix.startswith("demo-"):
        parser.error("--activity-prefix must start with demo-")
    if args.space_id:
        import uuid
        try:
            uuid.UUID(args.space_id)
        except ValueError:
            parser.error("--space-id must be a UUID")
    if args.action == "complete":
        if args.backup and args.apply:
            import django
            django.setup()
            from django.db import connection
            from .scope import backup_demo_sqlite
            print("BACKUP", backup_demo_sqlite(connection))
        if args.space_id or args.activity_prefix != "demo-":
            parser.error("--space-id/--activity-prefix are not supported for complete")
        from .__main__ import build_parser, run
        command = [
            "generate" if args.apply else "plan", "--domains", args.domains,
            "--count", str(args.count), "--profiles", str(args.profiles),
        ]
        if args.profile_username:
            command.extend(["--profile-username", args.profile_username])
        if args.grant_roles:
            command.append("--grant-roles")
        print("MAINTAIN complete: reuse existing domain generators")
        return run(build_parser().parse_args(command))

    if args.domains not in ("all", "activities"):
        parser.error("refresh/retire/restore target Activity; use --domains activities")
    if args.grant_roles:
        parser.error("--grant-roles is only meaningful for complete")

    import django
    django.setup()
    from django.db import connection, transaction
    from django.db.models import Q
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus, Occurrence
    from activities.services import update_activity_common
    from journeys.models import Journey
    from access.models import Access
    from events.models import Event
    from commerce.models import Offer
    from funding.models import FundingContribution
    from .scope import demo_activities, synthetic_owner

    if connection.vendor != "sqlite":
        parser.error("Maintenance is restricted to demonstration SQLite")
    if args.backup and args.apply:
        from .scope import backup_demo_sqlite
        print("BACKUP", backup_demo_sqlite(connection))

    candidates = demo_activities(Activity.objects).filter(
        slug__startswith=args.activity_prefix
    ).select_related(
        "owner_profile", "space", "space__created_by"
    ).order_by("created_at", "id")
    if args.profile_username:
        candidates = candidates.filter(
            Q(owner_profile__username=args.profile_username)
            | Q(space__created_by__username=args.profile_username)
        )
    if args.space_id:
        candidates = candidates.filter(space_id=args.space_id)
    if args.action == "retire":
        candidates = candidates.filter(
            status=ActivityStatus.PUBLISHED,
            created_at__lt=timezone.now() - timedelta(days=args.older_than_days),
        )
    elif args.action == "restore":
        candidates = candidates.filter(status=ActivityStatus.ARCHIVED)

    counters = Counter()
    samples = []
    for activity in candidates.iterator():
        if counters["eligible"] >= args.count:
            break
        if not synthetic_owner(activity):
            counters["out_of_scope"] += 1
            continue
        if args.action == "retire":
            # Never retire an Activity that may have downstream rights,
            # offers, claims, money or a visible occurrence/history.
            if (Occurrence.objects.filter(activity=activity).exists()
                or Journey.objects.filter(activity=activity).exists()
                or Access.objects.filter(activity=activity).exists()
                or Event.objects.filter(activity=activity).exists()
                or Offer.objects.filter(activity=activity).exists()
                or FundingContribution.objects.filter(
                    funding__activity=activity
                ).exists()):
                counters["protected_relationships"] += 1
                continue
            change = {"status": ActivityStatus.ARCHIVED}
        elif args.action == "restore":
            change = {"status": ActivityStatus.PUBLISHED}
        else:
            if activity.status not in (ActivityStatus.PUBLISHED, ActivityStatus.DRAFT):
                counters["inactive_skipped"] += 1
                continue
            text = editorial_text(args.edition, activity.pk)
            if activity.short_description == text:
                counters["unchanged"] += 1
                continue
            change = {"short_description": text}

        counters["eligible"] += 1
        if len(samples) < 8:
            samples.append(f"{activity.slug} -> {change}")
        if args.apply:
            with transaction.atomic():
                update_activity_common(activity=activity, **change)
            counters["updated"] += 1

    print("MAINTAIN", args.action, "APPLY" if args.apply else "PREVIEW")
    print("SUMMARY", dict(sorted(counters.items())))
    for sample in samples:
        print("SAMPLE", sample)
    print("No hard deletes, owner transfers, fake payments or changed audit timestamps.")


if __name__ == "__main__":
    main()
