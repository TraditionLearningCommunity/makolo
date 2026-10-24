"""Read-only audit of physical demo files and public/private delivery prerequisites."""
from collections import Counter
from django.core.management.base import BaseCommand

from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from presentations.asset_models import PresentationAsset
from presentations.media_models import PresentationMediaState, PresentationMediaUse


class Command(BaseCommand):
    help = "Inspect demo resource bytes, published media bindings and privacy; never modify data."

    def add_arguments(self, parser):
        parser.add_argument("--all-resources", action="store_true",
                            help="Include non-demo resources (potentially large).")
        parser.add_argument("--examples", type=int, default=12)

    def handle(self, *args, **options):
        limit = options["examples"]
        if limit < 0 or limit > 100:
            self.stderr.write("--examples must be between 0 and 100")
            return
        records = ActivityResource.objects.all()
        if not options["all_resources"]:
            records = records.filter(key__startswith="demo-")
        records = records.order_by("activity_id", "id")
        tally = Counter()
        samples = []
        for resource in records.iterator():
            if resource.kind != ResourceKind.FILE:
                tally[("resource", resource.kind, resource.status, "not-file")] += 1
                continue
            if not resource.file or not resource.file.name:
                state = "missing-reference"
            else:
                try:
                    state = "exists" if resource.file.storage.exists(resource.file.name) else "missing-bytes"
                except (OSError, ValueError) as exc:
                    state = "storage-error"
            tally[("resource", resource.mime_type or "unknown", resource.status, state)] += 1
            if state != "exists" and len(samples) < limit:
                samples.append(("resource", str(resource.pk), resource.key, state))
        uses = PresentationMediaUse.objects.filter(
            state=PresentationMediaState.PUBLISHED,
        ).select_related("asset").order_by("activity_id", "id")
        for use in uses.iterator():
            asset = use.asset
            stored = asset.private_file if asset.private_file else asset.file
            if not stored or not stored.name:
                state = "missing-reference"
            else:
                try:
                    state = "exists" if stored.storage.exists(stored.name) else "missing-bytes"
                except (OSError, ValueError):
                    state = "storage-error"
            tally[("presentation", asset.mime_type, use.state, state)] += 1
            if state != "exists" and len(samples) < limit:
                samples.append(("presentation", str(use.pk), str(asset.pk), state))
        self.stdout.write("READ ONLY; no file or database modifications")
        for labels, count in sorted(tally.items()):
            self.stdout.write(" | ".join(map(str, labels)) + f" : {count}")
        for kind, identity, info, problem in samples:
            self.stdout.write(f"EXAMPLE {kind} {identity} {info}: {problem}")
        self.stdout.write("NOTE: storage.exists is not proof of HTTP authorization or client rendering.")
