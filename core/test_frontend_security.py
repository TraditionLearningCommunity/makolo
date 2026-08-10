from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class FrontendSecurityHeaderTests(TestCase):
    def test_public_home_uses_strict_script_policy(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("worker-src 'self' blob:", csp)
        self.assertNotIn("'unsafe-eval'", csp)
        script_policy = next(
            directive for directive in csp.split("; ") if directive.startswith("script-src")
        )
        self.assertNotIn("'unsafe-inline'", script_policy)

    def test_browser_security_headers_are_present(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.headers["Permissions-Policy"], "camera=(self), microphone=(), geolocation=()")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_authenticated_shell_keeps_same_policy(self):
        user = User.objects.create_user(
            username="frontend-security-user",
            email="frontend-security@example.com",
            password="Strong-frontend-security-2026!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn("camera=(self)", response.headers["Permissions-Policy"])
