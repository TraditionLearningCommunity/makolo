"""Shared Appuis web surface: one template, actor-safe server owners."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization


class AppuisWebSurfaceTests(TestCase):
    def setUp(self):
        self.viewer = get_user_model().objects.create_superuser(
            username="appuis-viewer", email="appuis-viewer@example.test",
            password="Test-only-appuis-2026!",
        )
        self.client.force_login(self.viewer)

    def test_personal_appuis_uses_shared_template_and_real_empty(self):
        response = self.client.get(reverse("core:participant-appuis"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/appuis.html")
        self.assertContains(response, "Mes appuis")
        self.assertContains(response, "Aucun appui établi")

    def test_space_appuis_uses_same_template_with_space_actor(self):
        space = Organization.objects.create(
            name="Espace Appuis", created_by=self.viewer,
        )
        response = self.client.get(
            reverse("organizations:space-us-appuis", kwargs={"slug": space.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/appuis.html")
        self.assertContains(response, "Nos appuis")
        self.assertNotContains(response, "Mes appuis")

    def test_other_space_does_not_receive_an_unscoped_fallback(self):
        response = self.client.get(
            reverse("organizations:space-us-appuis", kwargs={"slug": "missing-space"})
        )
        self.assertEqual(response.status_code, 404)
