"""Shared Appuis web surface: one template, actor-safe server owners."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization
from loyalty.models import LoyaltyAccount, LoyaltyProgram


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

    def test_zero_balance_keeps_program_card_without_zero_metric(self):
        space = Organization.objects.create(
            name="Collectif Ateliers", created_by=self.viewer,
        )
        program = LoyaltyProgram.objects.create(
            organization=space, name="Avantages des participants",
            created_by=self.viewer,
        )
        LoyaltyAccount.objects.create(
            program=program, user=self.viewer, points_balance=0,
        )
        response = self.client.get(reverse("core:participant-appuis"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avantages des participants")
        self.assertContains(response, "Collectif Ateliers")
        self.assertNotContains(response, "0 points")
        self.assertNotContains(response, "ap-filters")
        self.assertContains(response, "ap-card")

    def test_space_scope_does_not_fall_back_to_another_profile(self):
        space = Organization.objects.create(
            name="Private Space", created_by=self.viewer,
        )
        outsider = get_user_model().objects.create_user(
            username="appuis-outsider", password="Test-only-2026!",
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("organizations:space-us-appuis",
                    kwargs={"slug": space.slug})
        )
        self.assertEqual(response.status_code, 404)
