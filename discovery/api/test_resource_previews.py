from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import UserProfile
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility

from .composition import (
    DISCOVERY_RESOURCE_INLINE_CHARS,
    DISCOVERY_RESOURCE_ACTIVITY_INLINE_BUDGET,
    _activity_resource_previews,
    _safe_public_http_url,
)


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
        UserProfile.objects.get_or_create(user=owner, defaults={"public_profile": True, "searchable": True})

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

    def test_long_public_text_has_bounded_inline_sample_and_full_owner_reader(self):
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
        self.assertEqual(row["text_content"], long_text[:DISCOVERY_RESOURCE_INLINE_CHARS])
        self.assertTrue(row["text_truncated"])
        self.assertEqual(
            row["read_url"],
            reverse("preparation:resource-text", kwargs={"resource_id": resources[0]["id"]}),
        )
        full = self.client.get(row["read_url"])
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content.decode("utf-8"), long_text)
        self.assertEqual(full["Cache-Control"], "private, no-store")
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

    def test_total_inline_budget_preserves_all_document_refs(self):
        for index in range(9):
            self._resource(f"long-{index:02d}", content="a" * 2000)
        resources = _activity_resource_previews([self.activity.pk])[str(self.activity.pk)]
        self.assertEqual(len(resources), 9)
        self.assertEqual(
            sum(len(item["text_content"]) for item in resources),
            DISCOVERY_RESOURCE_ACTIVITY_INLINE_BUDGET,
        )
        self.assertTrue(all(item["read_url"] for item in resources))
        self.assertTrue(all(item["text_truncated"] for item in resources))
        self.assertEqual(resources[-1]["text_content"], "")

    def test_owner_privacy_denies_even_metadata_and_read_endpoint(self):
        resource = self._resource("not-for-guests", content="No leak")
        row = _activity_resource_previews([self.activity.pk])[str(self.activity.pk)][0]
        self.assertIn("not-for-guests", row["title"])
        privacy = self.owner.profile
        privacy.public_profile = False
        privacy.save(update_fields=["public_profile"])
        self.assertEqual(_activity_resource_previews([self.activity.pk]), {})
        response = self.client.get(
            reverse("preparation:resource-text", kwargs={"resource_id": resource.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_untrusted_and_credentialed_external_urls_are_not_exposed(self):
        self.assertEqual(_safe_public_http_url("https://example.test/help"), "https://example.test/help")
        self.assertIsNone(_safe_public_http_url("javascript:alert(1)"))
        self.assertIsNone(_safe_public_http_url("https://user:pass@example.test/help"))
        self.assertIsNone(_safe_public_http_url("https://example.test\nmalformed"))
        self.assertIsNone(_safe_public_http_url("//example.test/unsafe"))
