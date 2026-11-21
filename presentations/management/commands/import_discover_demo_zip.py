"""Import the supplied N1 synthetic QA ZIP into an explicitly matching demo Activity.

No extraction, public URL guessing, or implicit publication of the private note.
Dry-run is the default; apply requires explicit acknowledgment.
"""
import hashlib
import json
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from preparation.models import ActivityResource, ResourceKind, ResourceVisibility
from preparation.services import create_resource, publish_resource
from presentations.asset_models import PresentationAsset
from presentations.asset_services import create_presentation_asset
from presentations.media_models import PresentationMediaPurpose, PresentationMediaState, PresentationMediaUse
from presentations.media_services import associate_presentation_media, publish_presentation_media


COVERS = ("cover-1.png", "cover-2.png", "cover-3.png")
FILES = (
    ("guide.pdf", "demo-zip-guide", "Guide synthétique", "application/pdf"),
    ("planning.csv", "demo-zip-planning", "Planning synthétique", "text/csv"),
    ("document-illustration.png", "demo-zip-image", "Document illustré synthétique", "image/png"),
    ("clip.mp4", "demo-zip-video", "Vidéo synthétique", "video/mp4"),
    ("extrait.wav", "demo-zip-audio", "Audio synthétique", "audio/wav"),
)
TEXTS = (
    ("infos.txt", "demo-zip-information", "Informations synthétiques", ResourceVisibility.PUBLIC),
    ("PRIVE-ne-pas-publier.txt", "demo-zip-private", "Note réservée synthétique", ResourceVisibility.PARTICIPANT),
)
REQUIRED = frozenset(("MANIFEST.json",) + COVERS + tuple(row[0] for row in FILES) + tuple(row[0] for row in TEXTS))


def normalize(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def read_demo_archive(path):
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if names != REQUIRED:
                raise CommandError("Le ZIP de démonstration contient des fichiers inattendus ou manquants.")
            infos = archive.infolist()
            if len(infos) != len(REQUIRED) or any(
                info.file_size > 10 * 1024 * 1024 or info.flag_bits & 1 for info in infos
            ) or sum(info.file_size for info in infos) > 40 * 1024 * 1024:
                raise CommandError("Archive trop grande, dupliquée ou chiffrée.")
            if archive.testzip() is not None:
                raise CommandError("Archive ZIP corrompue.")
            manifest = json.loads(archive.read("MANIFEST.json").decode("utf-8"))
            if (manifest.get("linked_to_database") is not False
                    or manifest.get("scenario") != "Clinique entrepreneuriale Yaounde"):
                raise CommandError("Manifeste incompatible avec ce jeu synthétique.")
            data = {name: archive.read(name) for name in REQUIRED if name != "MANIFEST.json"}
            for name in COVERS + tuple(row[0] for row in FILES):
                if not data[name]:
                    raise CommandError("Fichier de démonstration vide : " + name)
            for name, _, _, _ in TEXTS:
                data[name].decode("utf-8")
            return data, manifest["scenario"]
    except (BadZipFile, OSError, UnicodeError, ValueError, KeyError) as exc:
        raise CommandError(f"ZIP illisible ou invalide : {exc}") from exc


class Command(BaseCommand):
    help = "Import actual synthetic N1 files for a matching Activity, using canonical services."

    def add_arguments(self, parser):
        parser.add_argument("--zip", required=True)
        parser.add_argument("--activity-id", required=True)
        parser.add_argument("--operator", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-demo", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and not options["confirm_demo"]:
            raise CommandError("L'import exige --apply --confirm-demo sur la base synthétique.")
        actor = get_user_model().objects.filter(username=options["operator"]).first()
        activity = Activity.objects.filter(pk=options["activity_id"]).select_related("space").first()
        if actor is None or activity is None or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            raise CommandError("Activity ou opérateur invalide, ou autorité insuffisante.")
        if (activity.status != ActivityStatus.PUBLISHED
                or activity.visibility != ActivityVisibility.PUBLIC
                or (not activity.space_id and activity.owner_profile_id != actor.pk)):
            raise CommandError("Activity non publique, non publiée ou propriétaire incorrect.")
        path = Path(options["zip"])
        if not path.is_file():
            raise CommandError("ZIP introuvable.")
        data, scenario = read_demo_archive(path)
        if normalize(scenario) not in normalize(activity.title):
            raise CommandError("Le scénario du ZIP ne correspond pas au titre de l'Activity.")
        if not options["apply"]:
            self.stdout.write(
                f"DRY RUN: {activity.pk} | 3 images Presentation, "
                "5 fichiers et 2 textes (dont une note PARTICIPANT)."
            )
            return

        owner = {"owner_space": activity.space} if activity.space_id else {"owner_profile": actor}
        for index, filename in enumerate(COVERS, start=1):
            raw = data[filename]
            digest = hashlib.sha256(raw).hexdigest()
            asset = PresentationAsset.objects.filter(
                checksum=digest, mime_type="image/png", **owner,
            ).first()
            if asset is None or not (
                (asset.private_file and asset.private_file.storage.exists(asset.private_file.name))
                or (asset.file and asset.file.storage.exists(asset.file.name))
            ):
                asset = create_presentation_asset(
                    actor=actor, activity=activity, owner_space=activity.space,
                    uploaded_file=SimpleUploadedFile(filename, raw, content_type="image/png"),
                    protected=True,
                )
            use = PresentationMediaUse.objects.filter(
                activity=activity, asset=asset,
                occurrence__isnull=True, purpose=PresentationMediaPurpose.RECOGNIZE,
            ).order_by("created_at", "pk").first()
            if use is None:
                use = associate_presentation_media(
                    actor=actor, activity=activity, asset=asset,
                    purpose=PresentationMediaPurpose.RECOGNIZE,
                    position=20 + index,
                    alt_text=f"Illustration synthétique {index} — {scenario}"[:280],
                )
            if use.state == PresentationMediaState.DRAFT:
                publish_presentation_media(actor=actor, media_use=use)
            self.stdout.write(f"Presentation {use.pk}: {use.state}")

        for filename, key, title, mime in FILES:
            existing = ActivityResource.objects.filter(
                activity=activity, occurrence__isnull=True, key=key,
            ).exists()
            if existing:
                continue
            resource = create_resource(
                activity=activity, actor=actor, key=key, title=title,
                kind=ResourceKind.FILE,
                uploaded_file=SimpleUploadedFile(filename, data[filename], content_type=mime),
                visibility=ResourceVisibility.PUBLIC,
            )
            publish_resource(resource=resource, actor=actor)
            self.stdout.write(f"Resource {resource.pk}: {filename}")
        for filename, key, title, visibility in TEXTS:
            if ActivityResource.objects.filter(
                activity=activity, occurrence__isnull=True, key=key
            ).exists():
                continue
            resource = create_resource(
                activity=activity, actor=actor, key=key, title=title,
                kind=ResourceKind.TEXT, text_content=data[filename].decode("utf-8"),
                visibility=visibility,
            )
            publish_resource(resource=resource, actor=actor)
            self.stdout.write(f"Resource {resource.pk}: {key} ({visibility})")
