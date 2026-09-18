from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.web_navigation import safe_post_next


class M8EExperienceConvergenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="m8e-viewer",
            email="m8e-viewer@example.test",
            password="StrongPass2026!",
        )
        self.factory = RequestFactory()

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
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:participant-home"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        mobile_nav = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]
        for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
            self.assertIn(f"<span>{label}</span>", mobile_nav)
        self.assertIn(reverse("core:participant-home"), mobile_nav)
        self.assertIn(reverse("discovery:home"), mobile_nav)
        self.assertIn(reverse("core:makolo-mark"), mobile_nav)
        self.assertIn(reverse("core:participant-ongoing"), mobile_nav)
        self.assertIn(reverse("core:participant-me"), mobile_nav)
        self.assertNotIn(reverse("conversations:list"), mobile_nav)
        self.assertNotIn(reverse("account:profile"), mobile_nav)

    def test_new_personal_destinations_are_private(self):
        for route_name in ("core:participant-home", "core:participant-ongoing", "core:participant-me", "core:makolo-mark"):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("core:login"), response.url)
