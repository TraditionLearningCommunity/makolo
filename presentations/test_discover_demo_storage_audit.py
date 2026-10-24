from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from preparation.models import ActivityResource
from presentations.media_models import PresentationMediaUse


class DiscoverDemoStorageAuditTests(TestCase):
    def test_empty_database_is_safe_and_read_only(self):
        out = StringIO()
        before = (ActivityResource.objects.count(), PresentationMediaUse.objects.count())
        call_command("audit_discover_demo_storage", stdout=out)
        self.assertIn("READ ONLY", out.getvalue())
        self.assertEqual(before, (ActivityResource.objects.count(), PresentationMediaUse.objects.count()))
