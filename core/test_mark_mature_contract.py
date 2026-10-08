from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class MatureMarkContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mark-contract",
            email="mark-contract@test.local",
            password="Strong-Mark-Password-2026!",
        )
        self.client.force_login(self.user)

    def test_personal_mark_response_exposes_actor_context_and_safe_input_contract(self):
        response = self.client.post(
            reverse("personal-mark:mark"),
            {
                "input": {"kind": "text", "value": "Retrouve mon passeport."},
                "context": {
                    "selected": {"kind": "passport", "id": "known"},
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["actor_context"], {"kind": "profile"})
        self.assertEqual(data["accepted_input_kinds"], ["text"])
        self.assertEqual(
            data["request_context"]["selected"],
            {"kind": "passport"},
        )

    def test_personal_mark_rejects_client_authority_context(self):
        response = self.client.post(
            reverse("personal-mark:mark"),
            {
                "input": {"kind": "text", "value": "Ajoute Marie."},
                "context": {"permission": "admin", "role": "owner"},
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
