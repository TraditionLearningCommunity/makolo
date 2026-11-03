"""Django Web C4 lifecycle tests; normal CSRF templates, no secret reflection."""
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from authorization.platform_services import grant_platform_role
from intelligence.models import ProviderConnection, ProviderScope
from organizations.models import Organization


@patch.dict("os.environ", {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "web-only-c4-test-key"})
class C4WebConnectionTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="c4-web-owner", email="c4-web-owner@example.test", password="test",
        )
        self.other = User.objects.create_user(
            username="c4-web-other", email="c4-web-other@example.test", password="test",
        )
        UserProfile.objects.create(user=self.actor)
        UserProfile.objects.create(user=self.other)
        self.space = Organization.objects.create(
            slug="c4-web-space", name="C4 Web Space", created_by=self.actor,
        )
        grant_space_role(
            profile=self.actor, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.actor,
        )

    def test_profile_form_creates_and_removes_encrypted_connection(self):
        self.client.force_login(self.actor)
        url = reverse("core:participant-connections")
        page = self.client.get(f"{url}?offer=tavily")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Relier ce service")
        self.assertContains(page, 'name="api_key"')
        response = self.client.post(url, {
            "operation": "create", "consent": "yes", "provider": "tavily",
            "name": "Recherche personnelle", "model": "",
            "api_key": "C4-WEB-SECRET",
        })
        self.assertEqual(response.status_code, 302)
        row = ProviderConnection.objects.get(
            scope=ProviderScope.PROFILE, profile__user=self.actor,
        )
        self.assertEqual(row.name, "Recherche personnelle")
        displayed = self.client.get(f"{url}?tab=mine")
        self.assertContains(displayed, "Recherche personnelle")
        self.assertNotContains(displayed, "C4-WEB-SECRET")
        self.assertNotContains(displayed, "api.tavily.com")
        self.assertEqual(
            self.client.post(url, {
                "operation": "disconnect", "connection_id": str(row.pk),
                "confirm": "yes",
            }).status_code, 302,
        )
        self.assertFalse(ProviderConnection.objects.filter(pk=row.pk).exists())

    def test_other_profile_cannot_revoke_existing_connection(self):
        self.client.force_login(self.actor)
        url = reverse("core:participant-connections")
        self.client.post(url, {
            "operation": "create", "consent": "yes", "provider": "exa",
            "name": "Exa C4", "model": "", "api_key": "not-logged",
        })
        own = ProviderConnection.objects.get(name="Exa C4")
        self.client.force_login(self.other)
        response = self.client.post(url, {
            "operation": "disconnect",
            "connection_id": str(own.pk), "confirm": "yes",
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProviderConnection.objects.filter(pk=own.pk).exists())

    def test_space_web_mutation_requires_direct_space_manage(self):
        url = reverse("organizations:space-interoperability",
                      kwargs={"slug": self.space.slug})
        self.client.force_login(self.actor)
        response = self.client.post(url, {
            "operation": "create", "consent": "yes", "provider": "tavily",
            "name": "Service collectif C4", "model": "",
            "api_key": "space-secret",
        })
        self.assertEqual(response.status_code, 302)
        row = ProviderConnection.objects.get(name="Service collectif C4")
        self.assertEqual(row.scope, ProviderScope.SPACE)
        self.client.force_login(self.other)
        response = self.client.post(url, {
            "operation": "disconnect",
            "connection_id": str(row.pk), "confirm": "yes",
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProviderConnection.objects.filter(pk=row.pk).exists())

    def test_platform_web_management_isolated_to_platform_role(self):
        platform = User.objects.create_user(
            username="c4-web-platform", email="c4-web-platform@example.test",
            password="test",
        )
        grant_platform_role(
            profile=platform, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=platform,
        )
        url = reverse("platform_web:interoperability")
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(platform)
        self.assertEqual(self.client.get(url).status_code, 200)
        created = self.client.post(url, {
            "operation": "create", "consent": "yes", "provider": "exa",
            "name": "Plateforme Recherche C4", "model": "",
            "api_key": "WEB-PLATFORM-KEY",
        })
        self.assertEqual(created.status_code, 302)
        provider = ProviderConnection.objects.get(name="Plateforme Recherche C4")
        self.assertEqual(provider.scope, ProviderScope.PLATFORM)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.post(url, {
            "operation": "disconnect", "connection_id": str(provider.pk),
            "confirm": "yes",
        }).status_code, 403)
        self.assertTrue(ProviderConnection.objects.filter(pk=provider.pk).exists())

    def test_web_post_requires_csrf_not_only_an_authenticated_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("core:participant-connections")
        response = client.post(url, {
            "operation": "create", "consent": "yes", "provider": "tavily",
            "name": "Without CSRF", "model": "", "api_key": "SHOULD-NOT-STORE",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProviderConnection.objects.filter(name="Without CSRF").exists())

