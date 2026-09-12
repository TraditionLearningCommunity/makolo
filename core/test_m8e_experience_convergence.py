from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from core.web_navigation import safe_post_next


class M8EExperienceConvergenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="m8e-viewer",
            email="m8e-viewer@example.test",
            password="StrongPass2026!",
        )
        self.factory = RequestFactory()

    def _authenticated_request(self, url_name="core:participant-home"):
        path = reverse(url_name)
        request = self.factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return request

    def test_safe_post_next_keeps_same_host_context(self):
        request = self.factory.post(
            "/notifications/read/",
            {"next": "/me/journeys/?status=action"},
            HTTP_HOST="testserver",
        )

        destination = safe_post_next(request, fallback="core:participant-home")

        self.assertEqual(destination, "/me/journeys/?status=action")

    def test_safe_post_next_rejects_external_destination(self):
        request = self.factory.post(
            "/notifications/read/",
            {"next": "https://outside.example/phishing"},
            HTTP_HOST="testserver",
        )

        destination = safe_post_next(request, fallback="core:participant-home")

        self.assertEqual(destination, reverse("core:participant-home"))

    def test_mobile_shell_uses_mature_personal_destinations(self):
        html = render_to_string(
            "base/app.html",
            {"space_console": None},
            request=self._authenticated_request(),
        )
        mobile_nav = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]

        for label in ("Accueil", "Démarches", "Conversations", "Profil", "Plus"):
            self.assertIn(f"<span>{label}</span>", mobile_nav)
        self.assertNotIn("<span>Actions</span>", mobile_nav)
        self.assertNotIn("<span>Découvrir</span>", mobile_nav)
        self.assertIn(reverse("conversations:list"), mobile_nav)
        self.assertIn(reverse("account:profile"), mobile_nav)
