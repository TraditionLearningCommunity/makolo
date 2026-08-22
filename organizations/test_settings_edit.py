from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode

from .services import add_or_update_member, create_organization


User = get_user_model()


class SpaceSettingsEditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="settings-owner",
            email="settings-owner@makolo.test",
            password="Settings-2026!",
        )
        self.admin = User.objects.create_user(
            username="settings-admin",
            email="settings-admin@makolo.test",
            password="Settings-2026!",
        )
        self.activity_manager = User.objects.create_user(
            username="settings-activity-manager",
            email="settings-activity@makolo.test",
            password="Settings-2026!",
        )
        self.outsider = User.objects.create_user(
            username="settings-outsider",
            email="settings-outsider@makolo.test",
            password="Settings-2026!",
        )
        self.space = create_organization(
            creator=self.owner,
            name="Espace paramètres",
            description="Description initiale",
            contact_email="contact@example.com",
            country="CD",
            city="Lubumbashi",
        )
        add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.admin,
            role=SystemRoleCode.SPACE_ADMIN,
        )
        add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.activity_manager,
            role=SystemRoleCode.ACTIVITY_MANAGER,
        )
        self.edit_url = reverse("organizations:edit", kwargs={"slug": self.space.slug})

    def test_owner_can_open_and_update_space_settings(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.space.name)

        response = self.client.post(
            self.edit_url,
            {
                "name": "Espace paramètres mis à jour",
                "description": "Description corrigée",
                "website": "https://example.com",
                "contact_email": "contact@example.com",
                "contact_phone": "+243900000000",
                "country": "CD",
                "city": "Lubumbashi",
                "public_profile": "on",
            },
        )
        self.space.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("organizations:console-settings", kwargs={"slug": self.space.slug}),
        )
        self.assertEqual(self.space.name, "Espace paramètres mis à jour")
        self.assertEqual(self.space.description, "Description corrigée")

    def test_space_admin_can_open_settings_edit(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)

    def test_activity_manager_cannot_edit_global_space_settings(self):
        self.client.force_login(self.activity_manager)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_edit_space_settings(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 403)
