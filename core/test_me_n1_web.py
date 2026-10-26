"""N1 Web must render the same owner-projected personal capital as mobile."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PersonalMeN1WebTests(TestCase):
    def setUp(self):
        self.profile = get_user_model().objects.create_user(
            username="me-n1-preview",
            first_name="Amina",
            last_name="Test",
        )
        self.url = reverse("core:participant-me")

    def test_identity_and_empty_territories_remain_visible(self):
        self.client.force_login(self.profile)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mk-surface="me"')
        self.assertContains(response, "Amina Test")
        self.assertContains(response, "Passeport Makolo")
        self.assertContains(response, "Ce qui compte pour moi")
        self.assertContains(response, "Mes collectifs")
        self.assertContains(response, "Mes accès")
        self.assertContains(response, "Mes ressources")
        self.assertContains(response, "Aucune ressource pour le moment.")
        self.assertNotContains(response, "Profil complété à")
        self.assertNotContains(response, "AccessCredential")

    def test_web_n1_uses_an_explicit_stylesheet_and_preserves_owner_links(self):
        self.client.force_login(self.profile)
        response = self.client.get(self.url)
        self.assertContains(response, "css/me-n1.css")
        self.assertContains(response, reverse("core:participant-accesses"))
        self.assertContains(response, reverse("personal_assets:list"))
        self.assertContains(response, reverse("sharing:passport-me"))

    def test_anonymous_view_is_not_public(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_preview_pages_are_private_and_bounded(self):
        preview = reverse("personal-projections:me-preview", kwargs={"territory": "considerations"})
        self.assertNotEqual(self.client.get(preview).status_code, 200)
        self.client.force_login(self.profile)
        response = self.client.get(preview, {"offset": "6", "limit": "24"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["projection"], "personal.me.preview")
        data = response.json()["data"]
        self.assertEqual(data["territory"], "considerations")
        self.assertEqual(data["offset"], 6)
        self.assertEqual(data["collections"]["interests"]["items"], [])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_preview_rejects_scope_override_and_unbounded_requests(self):
        self.client.force_login(self.profile)
        preview = reverse("personal-projections:me-preview", kwargs={"territory": "resources"})
        self.assertEqual(self.client.get(preview, {"profile_id": "other"}).status_code, 400)
        self.assertEqual(self.client.get(preview, {"offset": -1}).status_code, 400)
        self.assertEqual(self.client.get(preview, {"limit": 1000}).status_code, 400)
        self.assertEqual(
            self.client.get(reverse("personal-projections:me-preview",
                kwargs={"territory": "unknown"})).status_code, 400
        )
