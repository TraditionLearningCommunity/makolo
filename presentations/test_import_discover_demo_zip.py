from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from activities.models import ActivityStatus
from activities.services import create_activity
from preparation.models import ActivityResource, ResourceVisibility
from presentations.media_models import PresentationMediaUse

from presentations.management.commands.seed_discover_media_demo import pdf_data


class ImportDiscoverZipTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = override_settings(MEDIA_ROOT=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user(
            username="zip-demo-operator", email="zip-demo@example.test"
        )
        UserProfile.objects.update_or_create(
            user=self.user, defaults={"public_profile": True, "searchable": True},
        )
        self.activity = create_activity(
            owner_profile=self.user, created_by=self.user,
            title="Clinique entrepreneuriale Yaounde — démo",
            status=ActivityStatus.PUBLISHED,
        )
        self.path = Path(self.directory.name) / "sample.zip"
        picture = Image.new("RGB", (128, 128), (82, 50, 219))
        image = BytesIO()
        picture.save(image, format="PNG")
        with ZipFile(self.path, "w") as archive:
            archive.writestr("MANIFEST.json",
                '{"linked_to_database": false, "scenario": "Clinique entrepreneuriale Yaounde"}')
            for name in ("cover-1.png", "cover-2.png", "cover-3.png", "document-illustration.png"):
                archive.writestr(name, image.getvalue())
            archive.writestr("guide.pdf", pdf_data(self.activity))
            archive.writestr("planning.csv", "date,place\n2026-12-01,Yaounde\n")
            archive.writestr("clip.mp4", b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isom")
            archive.writestr("extrait.wav", b"RIFF" + b"\x00" * 4 + b"WAVEfmt " + b"\x00" * 40)
            archive.writestr("infos.txt", "Informations publiques de demonstration")
            archive.writestr("PRIVE-ne-pas-publier.txt", "Informations reservees")

    def run_import(self, **kwargs):
        call_command(
            "import_discover_demo_zip", zip=str(self.path),
            activity_id=str(self.activity.pk), operator=self.user.username,
            stdout=StringIO(), **kwargs,
        )

    def test_requires_explicit_apply_and_matching_activity(self):
        self.run_import()
        self.assertEqual(ActivityResource.objects.count(), 0)
        with self.assertRaises(CommandError):
            self.run_import(apply=True)

    def test_zip_import_is_idempotent_and_private_note_is_not_public(self):
        self.run_import(apply=True, confirm_demo=True)
        self.assertEqual(ActivityResource.objects.count(), 7)
        # Same cover bytes deduplicate into a single asset/use; never force
        # three identical bindings from synthetic fixtures.
        self.assertEqual(PresentationMediaUse.objects.count(), 1)
        private = ActivityResource.objects.get(key="demo-zip-private")
        self.assertEqual(private.visibility, ResourceVisibility.PARTICIPANT)
        self.run_import(apply=True, confirm_demo=True)
        self.assertEqual(ActivityResource.objects.count(), 7)
        self.assertEqual(PresentationMediaUse.objects.count(), 1)
