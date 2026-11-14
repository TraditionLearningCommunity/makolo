"""Small integration gate for real demo files and canonical publication."""
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from activities.models import ActivityStatus
from activities.services import create_activity
from preparation.models import ActivityResource, ResourceKind, ResourceVisibility
from presentations.asset_models import PresentationAsset
from presentations.media_models import PresentationMediaState, PresentationMediaUse


class DiscoverMediaDemoSeedTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings_override = override_settings(MEDIA_ROOT=folder.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.owner = get_user_model().objects.create_user(
            username="demo-media-operator", email="demo-media@example.test"
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"public_profile": True, "searchable": True},
        )
        self.activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Atelier de démonstration réel",
            status=ActivityStatus.PUBLISHED,
        )

    def _seed(self):
        call_command(
            "seed_discover_media_demo", operator=self.owner.username,
            activity_id=[str(self.activity.pk)], stdout=StringIO(),
        )

    def test_media_are_real_published_accessible_and_idempotent(self):
        self._seed()
        self.assertEqual(
            PresentationMediaUse.objects.filter(
                activity=self.activity, state=PresentationMediaState.PUBLISHED
            ).count(), 2,
        )
        self.assertEqual(PresentationAsset.objects.count(), 2)
        for use in PresentationMediaUse.objects.filter(activity=self.activity):
            stored = use.asset.private_file or use.asset.file
            self.assertTrue(stored.storage.exists(stored.name))
            response = self.client.get(
                reverse("presentations:published-media-file", kwargs={"use_id": use.pk})
            )
            self.assertEqual(response.status_code, 200)
            response.close()
        files = ActivityResource.objects.filter(activity=self.activity)
        self.assertEqual(files.count(), 6)
        self.assertEqual(
            set(files.values_list("kind", flat=True)),
            {ResourceKind.FILE, ResourceKind.TEXT, ResourceKind.URL},
        )
        for resource in files.filter(kind=ResourceKind.FILE):
            self.assertTrue(resource.file.storage.exists(resource.file.name))
            response = self.client.get(
                reverse("preparation:resource-download", kwargs={"resource_id": resource.pk})
            )
            self.assertEqual(response.status_code, 200)
            response.close()
        private = files.get(visibility=ResourceVisibility.PARTICIPANT)
        self.assertNotEqual(private.visibility, ResourceVisibility.PUBLIC)
        self._seed()
        self.assertEqual(PresentationMediaUse.objects.filter(activity=self.activity).count(), 2)
        self.assertEqual(ActivityResource.objects.filter(activity=self.activity).count(), 6)

    def test_dry_run_creates_nothing(self):
        call_command(
            "seed_discover_media_demo", operator=self.owner.username,
            activity_id=[str(self.activity.pk)], dry_run=True, stdout=StringIO(),
        )
        self.assertFalse(PresentationAsset.objects.exists())
        self.assertFalse(ActivityResource.objects.exists())

    def test_private_activity_is_not_seeded(self):
        private_activity = create_activity(
            owner_profile=self.owner, created_by=self.owner,
            title="Activité privée", status=ActivityStatus.DRAFT,
        )
        with self.assertRaises(CommandError):
            call_command(
                "seed_discover_media_demo", operator=self.owner.username,
                activity_id=[str(private_activity.pk)], stdout=StringIO(),
            )
