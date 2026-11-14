"""Copy legacy public Presentation media-use files to protected storage.

Default is a non-destructive audit. Never assume that copying an old file
revokes its public MEDIA_ROOT URL; an explicit, guarded purge is required.
"""
import hashlib
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from presentations.asset_models import PresentationAsset
from presentations.models import ActivityPresentation


def _digest(field):
    checksum = hashlib.sha256()
    with field.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(part)
    return checksum.digest()


def _contains_reference(value, candidates):
    if isinstance(value, str):
        return any(token and token in value for token in candidates)
    if isinstance(value, dict):
        return any(_contains_reference(child, candidates) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_reference(child, candidates) for child in value)
    return False


def _editorial_uses_raw_asset(asset):
    """Conservative guard against breaking legacy MPS hero_image references."""
    try:
        raw_url = asset.file.url
    except (ValueError, OSError):
        raw_url = None
    needles = (raw_url, asset.file.name)
    for data in ActivityPresentation.objects.values_list(
        "editorial_data", flat=True
    ).iterator():
        if _contains_reference(data, needles):
            return True
    return False


class Command(BaseCommand):
    help = (
        "Audit/migrate legacy PresentationAsset.file linked to media uses. "
        "--apply copies to private storage; --purge-public additionally deletes "
        "unreferenced originals after checksum verification."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--purge-public", action="store_true")

    def handle(self, *args, **options):
        apply = options["apply"]
        purge = options["purge_public"]
        if purge and not apply:
            raise CommandError("--purge-public requires --apply")
        count = copied = purged = blocked = missing = 0
        # Include draft associations as well; a media use may become public
        # later without a new upload. Unrelated legacy assets are untouched.
        assets = (
            PresentationAsset.objects.filter(uses__isnull=False)
            .distinct().order_by("pk")
        )
        for asset in assets.iterator():
            if not asset.file:
                continue
            count += 1
            source = asset.file
            try:
                exists = source.storage.exists(source.name)
            except (OSError, ValueError):
                exists = False
            if not exists:
                missing += 1
                self.stderr.write(f"MISSING asset={asset.pk} public={source.name}")
                continue
            if not apply:
                self.stdout.write(f"LEGACY asset={asset.pk} public={source.name}")
                continue

            if not asset.private_file:
                extension = Path(source.name).suffix.lower()
                if extension not in {".png", ".jpg", ".jpeg"}:
                    raise CommandError(f"Unexpected legacy media extension: {asset.pk}")
                try:
                    before = _digest(source)
                    with source.open("rb") as handle:
                        asset.private_file.save(
                            f"legacy-{asset.pk}{extension}", File(handle),
                            save=False,
                        )
                    after = _digest(asset.private_file)
                    if before != after:
                        raise CommandError(
                            f"Private copy checksum mismatch for {asset.pk}"
                        )
                    asset.save(update_fields=["private_file"])
                except Exception:
                    if asset.private_file:
                        asset.private_file.storage.delete(asset.private_file.name)
                    raise
                copied += 1
                self.stdout.write(f"COPIED asset={asset.pk} private={asset.private_file.name}")

            if purge:
                if _editorial_uses_raw_asset(asset):
                    blocked += 1
                    self.stderr.write(
                        f"BLOCKED asset={asset.pk}: legacy editorial URL still referenced"
                    )
                    continue
                if _digest(source) != _digest(asset.private_file):
                    raise CommandError(
                        f"Original/private mismatch, refusing purge for {asset.pk}"
                    )
                source.storage.delete(source.name)
                if source.storage.exists(source.name):
                    raise CommandError(
                        f"Original still present after purge request: {asset.pk}"
                    )
                asset.file = ""
                asset.save(update_fields=["file"])
                purged += 1
                self.stdout.write(f"PURGED asset={asset.pk}")

        self.stdout.write(
            f"SUMMARY legacy={count} copied={copied} purged={purged} "
            f"blocked={blocked} missing={missing}"
        )
        if blocked or missing:
            self.stderr.write(
                "Review blocked/missing files and hosting/CDN rules manually; "
                "a copied file is NOT proof that its old public URL was revoked."
            )
