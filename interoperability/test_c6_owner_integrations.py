"""C6: real owner-led integrations without fictitious Connection or authority."""
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from notifications.models import PushEndpoint
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus


@override_settings(PAYMENTS_SANDBOX_ENABLED=True, MAKOLO_FIREBASE_PUSH_ENABLED=False)
class C6OwnerIntegrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="c6-owner", password="test",
        )
        self.other = User.objects.create_user(
            username="c6-other", password="test",
        )
        self.member = User.objects.create_user(
            username="c6-member", password="test",
        )
        self.operator = User.objects.create_user(
            username="c6-operator", password="test",
        )
        for user in (self.owner, self.other, self.member, self.operator):
            UserProfile.objects.create(user=user)
        self.space = Organization.objects.create(
            name="C6 Space", slug="c6-space", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.FINANCE, granted_by=self.owner,
        )
        grant_platform_role(
            profile=self.operator, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.operator,
        )
        team = Team.objects.create(
            organization=self.space, name="C6 member group", is_active=True,
        )
        TeamMembership.objects.create(
            team=team, user=self.member, status=TeamMembershipStatus.ACTIVE,
        )
        self.device = PushEndpoint.objects.create(
            user=self.owner, provider="fcm", platform="android",
            installation_id="C6-INSTALLATION-SECRET",
            token_hash="x" * 64,
            encrypted_token="C6-ENCRYPTED-SECRET",
            token_hint="C6-HIDDEN-HINT",
            active=True,
            app_version="1.0",
        )
        self.other_device = PushEndpoint.objects.create(
            user=self.other, provider="fcm", platform="ios",
            installation_id="OTHER-PRIVATE-DEVICE",
            token_hash="y" * 64,
            encrypted_token="OTHER-CREDENTIAL-SECRET",
            token_hint="OTHER-PRIVATE-HINT",
            active=True,
        )
        self.api = APIClient()

    def test_profile_domain_integrations_are_owned_and_not_generic_connections(self):
        self.api.force_authenticate(self.owner)
        res = self.api.get("/api/v1/me/interoperability/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Cache-Control"], "private, no-store")
        rows = res.data["domain_integrations"]
        push = next(row for row in rows if row["code"] == "notifications.push")
        self.assertEqual(push["active_count"], 1)
        self.assertTrue(push["connected"])
        self.assertFalse(push["available"])
        self.assertEqual(push["owner"], "notifications")
        self.assertEqual(push["links"]["manage"],
                         "/api/v1/notifications/push/endpoints/")
        sandbox = next(row for row in rows if row["code"] == "payments.sandbox")
        self.assertFalse(sandbox["connected"])
        self.assertEqual(sandbox["status"], "sandbox_only")
        self.assertFalse(any(
            row["owner"] == "notifications" or row["owner"] == "payments"
            for row in res.data["connections"]
        ))
        serialized = str(res.data)
        for forbidden in (
            "C6-INSTALLATION-SECRET", "C6-ENCRYPTED-SECRET",
            "C6-HIDDEN-HINT", str(self.device.pk), str(self.other_device.pk),
            "OTHER-PRIVATE-DEVICE", "OTHER-CREDENTIAL-SECRET",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_finance_authority_in_one_space_is_not_a_global_profile_payment_capability(self):
        # The owner has SPACE_OWNER and FINANCE in this Space. Personal
        # Connections still cannot promise manual payments in arbitrary contexts.
        self.api.force_authenticate(self.owner)
        personal = self.api.get("/api/v1/me/interoperability/")
        self.assertEqual(personal.status_code, 200)
        self.assertNotIn(
            "payments.manual",
            [row["code"] for row in personal.data["domain_integrations"]],
        )
        self.assertIn(
            "payments.sandbox",
            [row["code"] for row in personal.data["domain_integrations"]],
        )
        space = self.api.get(
            "/api/v1/organizations/workspaces/c6-space/interoperability/"
        )
        self.assertEqual(space.status_code, 200)
        self.assertIn(
            "payments.manual",
            [row["code"] for row in space.data["domain_integrations"]],
        )
        self.api.force_authenticate(self.operator)
        platform_personal = self.api.get("/api/v1/me/interoperability/")
        self.assertEqual(platform_personal.status_code, 200)
        self.assertNotIn(
            "payments.manual",
            [row["code"] for row in platform_personal.data["domain_integrations"]],
        )

    def test_other_profile_sees_only_own_push_integration(self):
        self.api.force_authenticate(self.other)
        res = self.api.get("/api/v1/me/interoperability/")
        self.assertEqual(res.status_code, 200)
        push = next(row for row in res.data["domain_integrations"]
                    if row["code"] == "notifications.push")
        self.assertEqual(push["active_count"], 1)
        self.assertNotIn(str(self.device.pk), str(res.data))
        self.assertNotIn("C6-INSTALLATION-SECRET", str(res.data))

    def test_space_finance_is_not_granted_by_membership_or_platform(self):
        url = "/api/v1/organizations/workspaces/c6-space/interoperability/"
        self.api.force_authenticate(self.owner)
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("payments.manual", [
            row["code"] for row in res.data["domain_integrations"]
        ])
        self.assertFalse(any(
            row["code"] == "notifications.push"
            for row in res.data["domain_integrations"]
        ))
        for user in (self.member, self.other, self.operator):
            self.api.force_authenticate(user)
            self.assertEqual(self.api.get(url).status_code, 404)

    def test_platform_isolation_and_no_external_psp_claim(self):
        self.api.force_authenticate(self.operator)
        res = self.api.get("/api/v1/platform/interoperability/")
        self.assertEqual(res.status_code, 200)
        rows = res.data["domain_integrations"]
        self.assertIn("payments.manual", [row["code"] for row in rows])
        self.assertFalse(any(row["connected"] for row in rows))
        self.assertFalse(any(row["code"] == "notifications.push" for row in rows))
        self.assertEqual(res.data["personal_modules_included"], False)
        self.assertEqual(res.data["space_modules_included"], False)

    def test_web_revoke_rechecks_profile_and_requires_csrf(self):
        url = reverse("core:participant-connections")
        web = Client(enforce_csrf_checks=True)
        web.force_login(self.owner)
        res = web.post(url, {
            "operation": "revoke_push", "endpoint_id": str(self.device.pk),
        })
        self.assertEqual(res.status_code, 403)
        self.device.refresh_from_db()
        self.assertTrue(self.device.active)

        self.client.force_login(self.owner)
        foreign = self.client.post(url, {
            "operation": "revoke_push", "endpoint_id": str(self.other_device.pk),
        })
        self.assertEqual(foreign.status_code, 404)
        self.other_device.refresh_from_db()
        self.assertTrue(self.other_device.active)
        success = self.client.post(url, {
            "operation": "revoke_push", "endpoint_id": str(self.device.pk),
        })
        self.assertEqual(success.status_code, 302)
        self.device.refresh_from_db()
        self.assertFalse(self.device.active)
        self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(PAYMENTS_SANDBOX_ENABLED=False)
    def test_no_phantom_payment_provider_without_owner_capability(self):
        self.api.force_authenticate(self.member)
        res = self.api.get("/api/v1/me/interoperability/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["domain_integrations"], [])
        self.assertEqual(res.data["connections"], [])
