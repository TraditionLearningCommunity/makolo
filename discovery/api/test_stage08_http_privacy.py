"""Stage 08: cache boundaries on viewer-dependent Discovery and Sharing API.

These tests are intentionally added without executing the CI stage (09).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class DiscoveryStage08HttpPrivacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="stage08-private", email="stage08@example.test",
            password="temporary-test-only",
        )

    def assert_not_cacheable(self, response):
        cache = response.get("Cache-Control", "")
        self.assertIn("no-store", cache)
        vary = {part.strip().lower() for part in
                response.get("Vary", "").split(",")}
        self.assertIn("authorization", vary)
        self.assertIn("cookie", vary)

    def test_public_discovery_has_no_shared_http_cache(self):
        self.assert_not_cacheable(
            self.client.get(reverse("discovery_api:items"))
        )

    def test_personal_discovery_and_watches_cannot_be_shared_in_cache(self):
        self.client.force_login(self.user)
        self.assert_not_cacheable(
            self.client.get(reverse("discovery_api:items"))
        )
        self.assert_not_cacheable(
            self.client.get(reverse("discovery_api:watches"))
        )

    def test_owner_denial_is_not_cacheable_as_a_permanent_empty_state(self):
        self.client.force_login(self.user)
        self.assert_not_cacheable(self.client.get(
            reverse("discovery_api:item-detail", kwargs={
                "family": "activity",
                "item_id": "11111111-2222-3333-4444-555555555555",
            }),
        ))

    def test_public_token_and_private_delivery_errors_do_not_cache(self):
        self.assert_not_cacheable(self.client.get(
            reverse("sharing_api:resolve", kwargs={"token": "not-a-real-token"}),
        ))
        self.assert_not_cacheable(self.client.get(
            reverse("sharing_api:delivery", kwargs={
                "delivery_id": "11111111-2222-3333-4444-555555555555",
            }),
        ))
