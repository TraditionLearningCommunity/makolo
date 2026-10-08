from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from core.platform_presentation import platform_modules_for
from recognition.models import RecognitionPolicy


User = get_user_model()


class PlatformWebContractTests(TestCase):
    def setUp(self):
        self.visitor = User.objects.create_user(
            username="platform-none", email="platform-none@test.local", password="x"
        )
        self.staff = User.objects.create_user(
            username="platform-staff", email="platform-staff@test.local", password="x",
            is_staff=True,
        )
        self.operator = User.objects.create_user(
            username="platform-operator", email="platform-operator@test.local", password="x"
        )
        self.curator = User.objects.create_user(
            username="platform-curator", email="platform-curator@test.local", password="x"
        )
        grant_platform_role(
            profile=self.operator, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.operator,
        )
        grant_platform_role(
            profile=self.curator, role=SystemRoleCode.OPPORTUNITY_CURATOR,
            granted_by=self.curator,
        )

    def test_anonymous_is_redirected_for_web_and_rejected_for_api(self):
        self.assertEqual(self.client.get("/platform/").status_code, 302)
        self.assertIn(self.client.get("/api/v1/platform/capabilities/").status_code, (401, 403))

    def test_staff_flag_is_not_permission(self):
        for actor in (self.staff, self.visitor):
            self.client.force_login(actor)
            self.assertEqual(self.client.get("/platform/").status_code, 403)
            self.assertEqual(self.client.get("/platform/system/").status_code, 403)
            self.assertEqual(self.client.get("/platform/recognition/").status_code, 403)
            self.assertEqual(self.client.get("/api/v1/platform/capabilities/").status_code, 403)

    def test_operator_has_canonical_modules_and_nocache(self):
        self.client.force_login(self.operator)
        response = self.client.get("/platform/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Platform")
        self.assertIn("no-store", response["Cache-Control"])
        keys = {module["key"] for module in platform_modules_for(self.operator)}
        self.assertIn("operations", keys)
        self.assertIn("interoperability", keys)
        self.assertEqual(
            keys, {item["key"] for item in
                   self.client.get("/api/v1/platform/capabilities/").data["modules"]}
        )

    def test_specialized_curator_has_no_operations_navigation_or_deeplinks(self):
        self.client.force_login(self.curator)
        response = self.client.get("/platform/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Curation")
        self.assertNotContains(response, 'href="/platform/system/"', html=False)
        self.assertNotContains(response, 'href="/platform/investigate/"', html=False)
        self.assertNotContains(response, 'href="/platform/recognition/"', html=False)
        self.assertEqual(self.client.get("/platform/system/").status_code, 403)
        self.assertEqual(self.client.get("/platform/interoperability/").status_code, 403)
        self.assertEqual(self.client.get("/platform/investigate/?q=secret").status_code, 403)

    def test_operator_investigation_is_explicitly_bounded(self):
        self.client.force_login(self.operator)
        response = self.client.get("/platform/investigate/?q=not-present")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operations uniquement")
        self.assertNotContains(response, "Credentials complets")

    def test_recognition_simulation_is_readonly_and_requires_permission(self):
        policy = RecognitionPolicy.objects.create(
            code="platform-test-policy", version=1, name="Test policy"
        )
        self.client.force_login(self.visitor)
        self.assertEqual(
            self.client.get(reverse("platform_web:recognition-simulation", kwargs={"pk": policy.pk})).status_code,
            403,
        )
        self.client.force_login(self.operator)
        with patch("recognition.simulation.simulate_policy", return_value={
            "signals": 0, "matches": 0, "projected_credits": 0, "objects": 0
        }):
            response = self.client.get(reverse(
                "platform_web:recognition-simulation", kwargs={"pk": policy.pk}
            ))
        self.assertEqual(response.status_code, 200)
        policy.refresh_from_db()
        self.assertEqual(policy.status, "draft")
        self.assertContains(response, "sans écriture ni publication")
