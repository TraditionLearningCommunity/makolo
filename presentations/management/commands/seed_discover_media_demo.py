"""Idempotently create real Discover N1 demo assets using canonical owners."""
import csv
import hashlib
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
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


def image_data(activity, index):
    digest = hashlib.sha256(f"{activity.pk}-{index}".encode()).digest()
    color = (50 + digest[0] // 3, 50 + digest[1] // 3, 90 + digest[2] // 3)
    picture = Image.new("RGB", (1200, 840), color)
    draw = ImageDraw.Draw(picture)
    draw.ellipse((130, 110, 810, 760), outline=(255, 238, 220), width=30)
    draw.rounded_rectangle((690, 120, 1030, 450), radius=60, fill=(255, 112, 77))
    draw.rectangle((0, 610, 1200, 840), fill=(25, 22, 54))
    title = activity.title.encode("ascii", "replace").decode()[:65]
    draw.text((65, 670), title, fill="white")
    draw.text((65, 745), f"MAKOLO DEMO - IMAGE {index}", fill="white")
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def pdf_data(activity):
    title = activity.title.encode("ascii", "replace").decode()[:65]
    title = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 50 740 Td (Makolo demo - {title}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(data)
    data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        data += f"{offset:010d} 00000 n \n".encode()
    data += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return bytes(data)


def csv_data(activity):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["scenario", "activity", "year"])
    writer.writerow(["demonstration", str(activity.pk), 2026])
    writer.writerow(["preparation", str(activity.pk), 2027])
    return buffer.getvalue().encode("utf-8")


def video_data():
    if not shutil.which("ffmpeg"):
        raise CommandError("ffmpeg absent : relancer sans --with-video.")
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "sample.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "color=c=0x5232db:s=640x360:r=24:d=2",
            "-c:v", "mpeg4", "-q:v", "4", "-movflags", "+faststart",
            str(output),
        ], check=True, capture_output=True)
        return output.read_bytes()


class Command(BaseCommand):
    help = "Seed real synthetic presentation images and resources for explicit demo Activities."

    def add_arguments(self, parser):
        parser.add_argument("--activity-id", action="append", required=True)
        parser.add_argument("--operator", required=True)
        parser.add_argument("--with-video", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["operator"]).first()
        if actor is None:
            raise CommandError("Opérateur introuvable.")
        ids = list(dict.fromkeys(options["activity_id"]))
        activities = list(Activity.objects.select_related("space").filter(pk__in=ids))
        if len(activities) != len(ids):
            raise CommandError("Activity inconnue.")
        for activity in activities:
            if activity.status != ActivityStatus.PUBLISHED or activity.visibility != ActivityVisibility.PUBLIC:
                raise CommandError("L'Activity de démonstration doit être publique et publiée.")
            if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
                raise CommandError("Opérateur sans autorité Activity.")
            if not activity.space_id and activity.owner_profile_id != actor.pk:
                raise CommandError("Le Profil doit posséder cette Activity personnelle.")
        if options["with_video"] and not shutil.which("ffmpeg"):
            raise CommandError("Installer ffmpeg ou omettre --with-video.")
        if options["dry_run"]:
            for activity in activities:
                self.stdout.write(f"{activity.pk}: 2 PNG + PDF + CSV + texte + ressource privée"
                                  + (" + MP4" if options["with_video"] else ""))
            return

        for activity in activities:
            for index in (1, 2):
                data = image_data(activity, index)
                owner = {"owner_space": activity.space} if activity.space_id else {"owner_profile": actor}
                asset = PresentationAsset.objects.filter(
                    checksum=hashlib.sha256(data).hexdigest(),
                    mime_type="image/png", **owner,
                ).first()
                if asset is None or not (
                    (asset.private_file and asset.private_file.storage.exists(asset.private_file.name))
                    or (asset.file and asset.file.storage.exists(asset.file.name))
                ):
                    asset = create_presentation_asset(
                        actor=actor, activity=activity, owner_space=activity.space,
                        uploaded_file=SimpleUploadedFile(
                            f"demo-{index}.png", data, content_type="image/png"
                        ), protected=True,
                    )
                use = PresentationMediaUse.objects.filter(
                    activity=activity, asset=asset,
                    occurrence__isnull=True,
                    purpose=PresentationMediaPurpose.RECOGNIZE,
                ).order_by("created_at", "pk").first()
                # Re-running the seed must not undo a deliberate retirement.
                if use is not None and use.state == PresentationMediaState.RETIRED:
                    self.stdout.write(f"Présentation retirée conservée {activity.pk}: {use.pk}")
                    continue
                if use is None:
                    use = associate_presentation_media(
                        actor=actor, activity=activity, asset=asset,
                        purpose=PresentationMediaPurpose.RECOGNIZE,
                        position=index,
                        alt_text=f"Illustration synthétique {index} - {activity.title}"[:280],
                    )
                if use.state == PresentationMediaState.DRAFT:
                    publish_presentation_media(actor=actor, media_use=use)
                self.stdout.write(f"Présentation {activity.pk}: {use.pk}")

            samples = [
                ("demo-guide-pdf", "Guide de démonstration", ResourceKind.FILE,
                 ResourceVisibility.PUBLIC, "application/pdf", pdf_data(activity)),
                ("demo-planning-csv", "Planning de démonstration", ResourceKind.FILE,
                 ResourceVisibility.PUBLIC, "text/csv", csv_data(activity)),
                ("demo-image-document", "Image documentaire de démonstration", ResourceKind.FILE,
                 ResourceVisibility.PUBLIC, "image/png", image_data(activity, 3)),
                ("demo-lien-externe", "Exemple de lien externe", ResourceKind.URL,
                 ResourceVisibility.PUBLIC, None, "https://example.org/"),
                ("demo-information", "Informations pratiques", ResourceKind.TEXT,
                 ResourceVisibility.PUBLIC, None, "Préparer les documents nécessaires."),
                ("demo-note-privee", "Note réservée", ResourceKind.TEXT,
                 ResourceVisibility.PARTICIPANT, None, "Réservée aux bénéficiaires."),
            ]
            if options["with_video"]:
                samples.append(("demo-video-mp4", "Vidéo de démonstration", ResourceKind.FILE,
                                ResourceVisibility.PUBLIC, "video/mp4", video_data()))
            for key, title, kind, visibility, mime, value in samples:
                if ActivityResource.objects.filter(
                    activity=activity, occurrence__isnull=True, key=key
                ).exists():
                    continue
                if kind == ResourceKind.FILE:
                    extension = {"application/pdf": "pdf", "text/csv": "csv", "video/mp4": "mp4", "image/png": "png"}[mime]
                    payload = {"uploaded_file": SimpleUploadedFile(
                        f"{key}.{extension}", value, content_type=mime,
                    )}
                elif kind == ResourceKind.URL:
                    payload = {"external_url": value}
                else:
                    payload = {"text_content": value}
                resource = create_resource(
                    actor=actor, activity=activity, key=key, title=title,
                    kind=kind, visibility=visibility, **payload,
                )
                publish_resource(resource=resource, actor=actor)
                self.stdout.write(f"Resource {activity.pk}: {resource.pk}")
