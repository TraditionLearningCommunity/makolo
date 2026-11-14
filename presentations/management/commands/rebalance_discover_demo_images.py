"""Rebalance only verifiably generated Discover demo Presentation images.

The tool never deletes assets or files and never touches documentary Resources.
Dry run is the default. Intended strictly for the synthetic/demo database.
"""
import hashlib

from django.core.management.base import BaseCommand, CommandError

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from presentations.management.commands.seed_discover_media_demo import image_data
from presentations.media_models import PresentationMediaPurpose, PresentationMediaState, PresentationMediaUse
from presentations.media_services import retire_presentation_media


def desired_demo_images(activity):
    """Stable demo variation, not a production presentation rule."""
    bucket = hashlib.sha256(f"discover-demo-v2:{activity.pk}".encode()).digest()[0] % 5
    return (0, 0, 1, 1, 2)[bucket]


class Command(BaseCommand):
    help = "Preview or retire redundant generated demo images without touching real media."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform the audited retirements.")
        parser.add_argument("--limit", type=int, default=0, help="Limit Activities for a small pilot (0 = all).")

    def handle(self, *args, **options):
        if options["limit"] < 0:
            raise CommandError("--limit must be >= 0.")
        activities = Activity.objects.filter(
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        ).select_related("owner_profile", "created_by", "space").order_by("pk")
        if options["limit"]:
            activities = activities[:options["limit"]]
        kept = retired = skipped = 0
        counts = {0: 0, 1: 0, 2: 0}
        for activity in activities:
            goal = desired_demo_images(activity)
            counts[goal] += 1
            uses = list(PresentationMediaUse.objects.filter(
                activity=activity,
                occurrence__isnull=True,
                purpose=PresentationMediaPurpose.RECOGNIZE,
                state=PresentationMediaState.PUBLISHED,
            ).select_related("asset"))
            matching = []
            for index in (1, 2):
                checksum = hashlib.sha256(image_data(activity, index)).hexdigest()
                candidates = [
                    use for use in uses
                    if use.asset.checksum == checksum
                    and use.asset.mime_type == "image/png"
                    and use.alt_text == f"Illustration synthétique {index} - {activity.title}"[:280]
                ]
                if len(candidates) == 1:
                    matching.append((index, candidates[0]))
            matching.sort(key=lambda pair: pair[0])
            to_retire = [use for index, use in matching if index > goal]
            kept += len(matching) - len(to_retire)
            if not to_retire:
                continue
            operator = next((
                user for user in (activity.owner_profile, activity.created_by)
                if user is not None
                and can(user, PermissionCode.ACTIVITY_MANAGE, activity=activity)
                and (activity.space_id is not None or activity.owner_profile_id == user.pk)
            ), None)
            if operator is None:
                skipped += len(to_retire)
                self.stdout.write(f"SKIP {activity.pk}: no authorized operator")
                continue
            for use in to_retire:
                self.stdout.write(f"{'RETIRE' if options['apply'] else 'WOULD RETIRE'} {use.pk} activity={activity.pk} goal={goal}")
                if options["apply"]:
                    retire_presentation_media(actor=operator, media_use=use)
                retired += 1
        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY RUN'}: "
            f"target distribution={counts}; matched kept={kept}; "
            f"{'retired' if options['apply'] else 'planned retirements'}={retired}; "
            f"skipped={skipped}"
        )
