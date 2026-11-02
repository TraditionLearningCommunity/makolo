"""C8 security: even denied and invalid owner responses are never cacheable."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from organizations.models import Organization


class PrivateInteropErrorBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="c8-unprivileged", password="test",
        )
        UserProfile.objects.create(user=self.user)
        self.space = Organization.objects.create(
            name="C8 Restricted Space", slug="c8-restricted-space",
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_space_denials_are_not_publicly_cacheable(self):
        for path in (
            "/api/v1/organizations/workspaces/c8-restricted-space/interoperability/",
            "/api/v1/organizations/workspaces/c8-restricted-space/intelligence/connections/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_platform_denials_are_not_cacheable(self):
        for path in (
            "/api/v1/platform/interoperability/",
            "/api/v1/platform/intelligence/connections/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_invalid_owner_mutation_has_no_cache_or_sensitive_echo(self):
        response = self.client.post(
            "/api/v1/me/intelligence/connections/",
            {"provider": "not-configured", "api_key": "C8-NOT-STORE",
             "consent": True, "name": "Invalid"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("C8-NOT-STORE", str(response.data))

    def test_profile_read_is_always_private(self):
        response = self.client.get("/api/v1/me/interoperability/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
