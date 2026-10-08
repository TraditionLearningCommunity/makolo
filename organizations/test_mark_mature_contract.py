from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization


class MatureSpaceMarkContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mark-space-owner",
            email="mark-space-owner@test.local",
            password="Strong-Mark-Space-2026!",
        )
        self.space = Organization.objects.create(
            name="Mark Space",
            slug="mark-space",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.client.force_login(self.owner)

    def test_space_mark_response_exposes_server_resolved_actor_context(self):
        response = self.client.post(
            reverse("organizations:space-mark-api", kwargs={"slug": self.space.slug}),
            {
                "input": {"kind": "text", "value": "Ouvre le Jour J."},
                "context": {
                    "selected": {"kind": "occurrence", "id": "not-used"},
                    "space_id": "spoofed",
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("space_id", response.json())

        response = self.client.post(
            reverse("organizations:space-mark-api", kwargs={"slug": self.space.slug}),
            {
                "input": {"kind": "text", "value": "Ouvre le Jour J."},
                "context": {
                    "selected": {"kind": "occurrence", "id": "not-used"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(
            data["actor_context"],
            {"kind": "space", "slug": self.space.slug},
        )
        self.assertEqual(data["accepted_input_kinds"], ["text"])

    def test_space_mark_does_not_accept_client_permission(self):
        response = self.client.post(
            reverse("organizations:space-mark-api", kwargs={"slug": self.space.slug}),
            {
                "input": {"kind": "text", "value": "Ajoute Marie."},
                "context": {"permission": "space.owner"},
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("permission", response.json())
