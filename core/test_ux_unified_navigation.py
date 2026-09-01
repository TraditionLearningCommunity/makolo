from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse


class UnifiedNavigationUxTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ux-navigation",
            email="ux-navigation@example.test",
            password="test-password",
        )
        self.factory = RequestFactory()

    def _request(self, url_name="core:participant-home"):
        path = reverse(url_name)
        request = self.factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return request

    def test_personal_navigation_is_intention_based(self):
        html = render_to_string(
            "partials/navigation_links.html",
            {"request": self._request(), "space_console": None},
        )

        for label in ("Accueil", "Mes démarches", "Mes accès", "Historique", "Découvrir"):
            self.assertIn(label, html)
        self.assertNotIn(">Services<", html)
        self.assertNotIn(">Opportunités<", html)
        self.assertNotIn(">Abonnement<", html)

    def test_personal_account_menu_contains_billing_entry(self):
        html = render_to_string(
            "partials/navbar.html",
            {"request": self._request(), "space_console": None},
        )

        self.assertIn("Mes Espaces", html)
        self.assertIn("Mon profil et réglages", html)
        self.assertIn("Mon abonnement et facturation", html)
        self.assertIn("Changer de compte", html)
        self.assertIn("Se déconnecter", html)

    def test_space_navigation_uses_explicit_subscription_authority_label(self):
        request = self._request()
        space = SimpleNamespace(slug="demo-space", name="Demo Space")
        console = SimpleNamespace(
            navigation_groups=(
                {
                    "label": "Espace",
                    "items": (
                        {
                            "key": "subscription",
                            "label": "Abonnement",
                            "icon": "layers-3",
                            "url": "/spaces/demo-space/subscription/",
                        },
                    ),
                },
            )
        )
        html = render_to_string(
            "partials/navigation_links.html",
            {
                "request": request,
                "space_console": console,
                "space": space,
                "console_module_key": "subscription",
            },
        )

        self.assertIn("Abonnement de l’espace", html)
        self.assertNotIn("Mon abonnement et facturation", html)
