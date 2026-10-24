"""Safely retire broken, published, synthetic file references via Preparation.

Does not restore unknown bytes, replace files, infer third-party URLs, or remove rows.
Dry-run is the default; --apply requires explicit acknowledgement of a demo DB.
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from preparation.models import ActivityResource, ResourceKind, ResourceStatus
from preparation.services import retire_resource


class Command(BaseCommand):
    help = "Reconcile missing demo Resource files without affecting genuine content."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-demo", action="store_true",
                            help="Confirm the selected database is synthetic/demo only.")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--examples", type=int, default=12)

    def handle(self, *args, **options):
        if options["apply"] and not options["confirm_demo"]:
            raise CommandError("--apply exige --confirm-demo (base synthétique seulement).")
        if options["limit"] < 0 or not 0 <= options["examples"] <= 100:
            raise CommandError("Invalid --limit or --examples.")
        qs = ActivityResource.objects.filter(
            key__startswith="demo-", kind=ResourceKind.FILE,
            status=ResourceStatus.PUBLISHED,
        ).select_related("activity", "activity__owner_profile", "activity__created_by", "activity__space")
        qs = qs.order_by("activity_id", "pk")
        if options["limit"]:
            qs = qs[:options["limit"]]
        totals = Counter()
        examples = 0
        # Snapshot rows before any status transitions (safe with SQLite cursors).
        for resource in list(qs):
            if not resource.file or not resource.file.name:
                totals["without_reference"] += 1
                continue
            try:
                missing = not resource.file.storage.exists(resource.file.name)
            except (OSError, ValueError):
                totals["storage_error"] += 1
                continue
            if not missing:
                totals["available"] += 1
                continue

            activity = resource.activity
            candidates = (activity.owner_profile, activity.created_by, resource.created_by)
            from authorization.constants import PermissionCode
            from authorization.services import can
            operator = next((
                actor for actor in candidates
                if actor is not None
                and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
                and (activity.space_id is not None or activity.owner_profile_id == actor.pk)
            ), None)
            if operator is None:
                totals["unauthorized_skipped"] += 1
                continue
            if examples < options["examples"]:
                self.stdout.write(
                    f"{'RETIRE' if options['apply'] else 'WOULD RETIRE'} "
                    f"{resource.pk} {resource.key} ({resource.mime_type})"
                )
                examples += 1
            if options["apply"]:
                # Revalidate under the canonical service's permission and state checks.
                retire_resource(resource=resource, actor=operator)
            totals["retired" if options["apply"] else "planned"] += 1
        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY RUN'}: "
            + ", ".join(f"{key}={value}" for key, value in sorted(totals.items()))
        )
