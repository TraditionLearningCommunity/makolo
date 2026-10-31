"""Retire only exact, unmodified documentary fixtures from Discover N1 demo.

Dry run by default. Does not delete any Resource, asset or stored file.
"""
import hashlib

from django.core.management.base import BaseCommand, CommandError

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from preparation.services import retire_resource
from presentations.management.commands.seed_discover_media_demo import csv_data, image_data, pdf_data


def desired_resource_keys(activity):
    """Stable fixture variety; no production constraint."""
    bucket = hashlib.sha256(f"discover-resources-v1:{activity.pk}".encode()).digest()[0] % 6
    return (
        frozenset(),
        frozenset({"demo-information", "demo-lien-externe"}),
        frozenset({"demo-guide-pdf", "demo-planning-csv"}),
        frozenset({"demo-image-document", "demo-information"}),
        frozenset({"demo-guide-pdf", "demo-information", "demo-note-privee"}),
        frozenset({"demo-guide-pdf", "demo-planning-csv", "demo-image-document",
                   "demo-lien-externe", "demo-information", "demo-note-privee"}),
    )[bucket]


def matches_fixture(resource, activity):
    expected = {
        "demo-guide-pdf": (ResourceKind.FILE, ResourceVisibility.PUBLIC,
                           "Guide de démonstration", "application/pdf", pdf_data(activity)),
        "demo-planning-csv": (ResourceKind.FILE, ResourceVisibility.PUBLIC,
                              "Planning de démonstration", "text/csv", csv_data(activity)),
        "demo-image-document": (ResourceKind.FILE, ResourceVisibility.PUBLIC,
                                "Image documentaire de démonstration", "image/png", image_data(activity, 3)),
        "demo-lien-externe": (ResourceKind.URL, ResourceVisibility.PUBLIC,
                              "Exemple de lien externe", "", "https://example.org/"),
        "demo-information": (ResourceKind.TEXT, ResourceVisibility.PUBLIC,
                              "Informations pratiques", "", "Préparer les documents nécessaires."),
        "demo-note-privee": (ResourceKind.TEXT, ResourceVisibility.PARTICIPANT,
                             "Note réservée", "", "Réservée aux bénéficiaires."),
    }.get(resource.key)
    if expected is None or resource.kind != expected[0] or resource.visibility != expected[1]:
        return False
    if resource.title != expected[2] or resource.version != 1 or resource.supersedes_id:
        return False
    if resource.kind == ResourceKind.FILE:
        return (resource.mime_type == expected[3]
                and resource.content_hash == hashlib.sha256(expected[4]).hexdigest()
                and resource.size == len(expected[4]))
    if resource.kind == ResourceKind.TEXT:
        return resource.text_content == expected[4]
    return resource.external_url == expected[4]


class Command(BaseCommand):
    help = "Diversify only exact Discover demo Resource fixtures (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        if options["limit"] < 0:
            raise CommandError("--limit doit être positif.")
        activities = Activity.objects.filter(
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        ).select_related("owner_profile", "created_by", "space").order_by("pk")
        if options["limit"]:
            activities = activities[:options["limit"]]
        planned = skipped = kept = 0
        for activity in activities:
            wanted = desired_resource_keys(activity)
            operator = next((
                user for user in (activity.owner_profile, activity.created_by)
                if user is not None
                and can(user, PermissionCode.ACTIVITY_MANAGE, activity=activity)
                and (activity.space_id is not None or activity.owner_profile_id == user.pk)
            ), None)
            candidates = ActivityResource.objects.filter(
                activity=activity, occurrence__isnull=True, version=1,
                status=ResourceStatus.PUBLISHED, key__startswith="demo-",
            )
            for resource in candidates:
                if resource.key in wanted:
                    kept += 1
                    continue
                if not matches_fixture(resource, activity) or operator is None:
                    skipped += 1
                    self.stdout.write(f"SKIP {resource.pk}: altered fixture or unauthorized")
                    continue
                self.stdout.write(f"{'RETIRE' if options['apply'] else 'WOULD RETIRE'} {resource.pk} {resource.key} activity={activity.pk}")
                if options["apply"]:
                    retire_resource(resource=resource, actor=operator)
                planned += 1
        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY RUN'}: "
            f"retirements={planned} kept={kept} skipped={skipped}"
        )
