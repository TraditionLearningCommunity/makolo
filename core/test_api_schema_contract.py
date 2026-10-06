from django.contrib.auth import get_user_model
from django.test import TestCase


class ApiSchemaContractTests(TestCase):
    def test_authenticated_openapi_schema_is_machine_readable(self):
        user = get_user_model().objects.create_user(username="schema-contract-user")
        self.client.force_login(user)

        response = self.client.get(
            "/api/v1/schema/",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(str(payload.get("openapi", "")).startswith("3."))
        self.assertIn("/api/v1/me/now/", payload.get("paths", {}))
        self.assertIn("/api/v1/discovery/items/", payload.get("paths", {}))
