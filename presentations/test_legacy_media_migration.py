"""The legacy media migration is opt-in and protects existing MPS URLs."""
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse
from django.test import TestCase, override_settings

from activities.models import Activity, ActivityStatus, ActivityVisibility
from presentations.asset_models import PresentationAsset
from presentations.enums import Provenance
from presentations.management.commands.harden_presentation_media_assets import (
    _contains_reference,
)
from presentations.media_models import PresentationMediaPurpose, PresentationMediaUse
from presentations.media_services import publish_presentation_media
from accounts.models import UserProfile


class LegacyPresentationMediaMigrationTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        setting = override_settings(MEDIA_ROOT=self.tmp.name)
        setting.enable()
        self.addCleanup(setting.disable)
        owner = get_user_model().objects.create_user(
            username="presentation-migration-owner", password="test-strong",
        )
        UserProfile.objects.create(user=owner, public_profile=True, searchable=True)
        activity = Activity.objects.create(
            owner_profile=owner, created_by=owner,
            title="Legacy presentation", status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.asset = PresentationAsset(
            provenance=Provenance.USER, owner_profile=owner, uploaded_by=owner,
            mime_type="image/png", size=6, checksum="a" * 64,
        )
        self.asset.file.save("legacy.png", ContentFile(b"legacy"), save=False)
        self.asset.save()
        self.use = PresentationMediaUse.objects.create(
            activity=activity, asset=self.asset, created_by=owner,
            purpose=PresentationMediaPurpose.RECOGNIZE,
            alt_text="Image existante",
        )

    def test_dry_run_does_not_copy_or_delete(self):
        out = StringIO()
        call_command("harden_presentation_media_assets", stdout=out)
        self.asset.refresh_from_db()
        self.assertFalse(bool(self.asset.private_file))
        self.assertTrue(self.asset.file.storage.exists(self.asset.file.name))
        self.assertIn("LEGACY asset=", out.getvalue())

    def test_copy_then_explicit_purge_preserves_private_bytes(self):
        call_command("harden_presentation_media_assets", "--apply", stdout=StringIO())
        self.asset.refresh_from_db()
        self.addCleanup(
            lambda: self.asset.private_file.storage.delete(self.asset.private_file.name)
            if self.asset.private_file else None
        )
        self.assertTrue(self.asset.private_file.storage.exists(self.asset.private_file.name))
        with self.asset.private_file.open("rb") as stream:
            self.assertEqual(stream.read(), b"legacy")
        self.assertTrue(self.asset.file.storage.exists(self.asset.file.name))

        call_command(
            "harden_presentation_media_assets",
            "--apply", "--purge-public", stdout=StringIO(),
        )
        self.asset.refresh_from_db()
        self.assertFalse(bool(self.asset.file))
        self.assertTrue(self.asset.private_file.storage.exists(self.asset.private_file.name))
        publish_presentation_media(actor=self.use.created_by, media_use=self.use)
        response = self.client.get(
            reverse("presentations:published-media-file", kwargs={"use_id": self.use.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"legacy")
        response.close()

    def test_legacy_editorial_reference_blocks_public_deletion(self):
        # Model-level legacy URL references can outlive the media-use relation.
        with patch(
            "presentations.management.commands.harden_presentation_media_assets._editorial_uses_raw_asset",
            return_value=True,
        ):
            err = StringIO()
            call_command(
                "harden_presentation_media_assets",
                "--apply", "--purge-public",
                stdout=StringIO(), stderr=err,
            )
        self.asset.refresh_from_db()
        self.addCleanup(
            lambda: self.asset.private_file.storage.delete(self.asset.private_file.name)
            if self.asset.private_file else None
        )
        self.assertTrue(self.asset.file.storage.exists(self.asset.file.name))
        self.assertTrue(bool(self.asset.private_file))
        self.assertIn("BLOCKED", err.getvalue())

    def test_nested_legacy_editorial_references_are_detected(self):
        self.assertTrue(_contains_reference(
            {"image": [{"src": "/media/presentations/assets/old.png"}]},
            ("/media/presentations/assets/old.png",),
        ))
        self.assertFalse(_contains_reference(
            {"image": [{"src": "/safe/new.png"}]},
            ("/media/presentations/assets/old.png",),
        ))
