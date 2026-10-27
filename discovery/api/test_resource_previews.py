from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility

from .composition import _activity_resource_previews


class DiscoveryDocumentaryPreviewTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            username="discover-doc-preview", email="preview@example.test",
            password="test-strong-secret",
        )
        self.activity = Activity.objects.create(
            owner_profile=owner, created_by=owner,
            title="Démonstration du catalogue documentaire",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.owner = owner

    def _resource(self, key, *, kind=ResourceKind.TEXT, visibility=ResourceVisibility.PUBLIC,
                  content="Instructions", external_url=""):
        return ActivityResource.objects.create(
            activity=self.activity, created_by=self.owner,
            title=key, key=key, kind=kind,
            text_content=content if kind == ResourceKind.TEXT else "",
            external_url=external_url if kind == ResourceKind.URL else "",
            status=ResourceStatus.PUBLISHED, visibility=visibility,
            published_at=timezone.now(),
        )

    def test_public_text_is_complete_without_fake_url(self):
        long_text = "Préparation accessible. " * 180
        self._resource("instructions", content=long_text)
        public = self._resource(
            "note-privee", content="Uniquement pour les participants",
            visibility=ResourceVisibility.PARTICIPANT,
        )
        resources = _activity_resource_previews([self.activity.pk])[str(self.activity.pk)]
        self.assertEqual(len(resources), 1)
        row = resources[0]
        self.assertEqual(row["kind"], ResourceKind.TEXT)
        self.assertEqual(row["text_content"], long_text)
        self.assertFalse(row["text_truncated"])
        self.assertIsNone(row["download_url"])
        self.assertIsNone(row["external_url"])
        self.assertNotIn(str(public.pk), repr(resources))
        self.assertNotIn("Uniquement pour les participants", repr(resources))

    def test_external_url_only_allows_http_or_https(self):
        approved = self._resource("lien-ok", kind=ResourceKind.URL, external_url="https://example.org/")
        legacy = self._resource("lien-legacy", kind=ResourceKind.URL, external_url="https://example.org/")
        ActivityResource.objects.filter(pk=legacy.pk).update(external_url="javascript:alert(1)")
        resources = _activity_resource_previews([self.activity.pk])[str(self.activity.pk)]
        by_id = {r["id"]: r for r in resources}
        self.assertEqual(by_id[str(approved.pk)]["external_url"], "https://example.org/")
        self.assertIsNone(by_id[str(legacy.pk)]["external_url"])

    def test_resource_collection_has_no_silent_presentation_limit(self):
        count = 13
        for number in range(count):
            self._resource(f"sample-{number:02d}")
        resources = _activity_resource_previews([self.activity.pk])[str(self.activity.pk)]
        self.assertEqual(len(resources), count)
        self.assertEqual(
            {resource["title"] for resource in resources},
            {f"sample-{number:02d}" for number in range(count)},
        )
