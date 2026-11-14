from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from activities.services import create_activity
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from preparation.services import create_resource, publish_resource


class ReconcileDemoMissingFilesTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="reconcile-owner", email="reconcile@example.test", password="DemoPass2026!"
        )
        self.activity = create_activity(
            owner_profile=self.actor, created_by=self.actor, title="Test synthétique"
        )

    def resource(self, key):
        resource = create_resource(
            activity=self.activity, actor=self.actor, key=key,
            title=key, kind=ResourceKind.FILE,
            uploaded_file=SimpleUploadedFile(
                "guide.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf"
            ), visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.actor)
        return resource

    def test_dry_run_and_missing_only_demo_reconciled(self):
        missing = self.resource("demo-missing")
        genuine = self.resource("official-guide")
        available = self.resource("demo-available")
        missing.file.storage.delete(missing.file.name)
        genuine.file.storage.delete(genuine.file.name)
        call_command("reconcile_discover_demo_files", stdout=StringIO())
        missing.refresh_from_db()
        self.assertEqual(missing.status, ResourceStatus.PUBLISHED)
        with self.assertRaises(CommandError):
            call_command("reconcile_discover_demo_files", apply=True, stdout=StringIO())
        call_command(
            "reconcile_discover_demo_files", apply=True, confirm_demo=True,
            stdout=StringIO(),
        )
        missing.refresh_from_db()
        genuine.refresh_from_db()
        available.refresh_from_db()
        self.assertEqual(missing.status, ResourceStatus.RETIRED)
        self.assertEqual(genuine.status, ResourceStatus.PUBLISHED)
        self.assertEqual(available.status, ResourceStatus.PUBLISHED)
        self.assertTrue(ActivityResource.objects.filter(pk=missing.pk).exists())
        again = StringIO()
        call_command(
            "reconcile_discover_demo_files", apply=True, confirm_demo=True,
            stdout=again,
        )
        self.assertNotIn("retired=", again.getvalue())
