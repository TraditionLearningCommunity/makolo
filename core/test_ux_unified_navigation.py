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

    def test_personal_sidebar_uses_only_mature_primary_anchors(self):
        html = render_to_string(
            "partials/sidebar.html",
            {"request": self._request(), "space_console": None},
        )

        for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
            self.assertIn(f"<span>{label}</span>", html)
        for legacy_label in ("Accueil", "Mes démarches", "Conversations", "Profil", "Mes Espaces", "Mes accès", "Bibliothèque", "Mes veilles", "Historique"):
            self.assertNotIn(f"<span>{legacy_label}</span>", html)

    def test_discover_is_a_primary_destination_without_a_second_sidebar_cta(self):
        request = self._request()
        sidebar_html = render_to_string(
            "partials/sidebar.html",
            {"request": request, "space_console": None},
        )
        discover_href = f'href="{reverse("discovery:home")}"'

        self.assertEqual(sidebar_html.count(discover_href), 1)
        self.assertIn("<span>Découvrir</span>", sidebar_html)
        self.assertNotIn("Trouver une prochaine possibilité", sidebar_html)

    def test_secondary_personal_pages_do_not_become_primary_destinations(self):
        conversations_html = render_to_string(
            "partials/sidebar.html",
            {"request": self._request("conversations:list"), "space_console": None},
        )
        profile_html = render_to_string(
            "partials/sidebar.html",
            {"request": self._request("account:profile"), "space_console": None},
        )

        for html in (conversations_html, profile_html):
            for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
                self.assertIn(f"<span>{label}</span>", html)
            self.assertNotIn("<span>Conversations</span>", html)
            self.assertNotIn("<span>Profil</span>", html)

    def test_personal_account_menu_contains_context_and_account_actions(self):
        html = render_to_string(
            "partials/navbar.html",
            {"request": self._request(), "space_console": None},
        )

        self.assertIn("Agir comme", html)
        self.assertIn("Compte et paramètres", html)
        self.assertIn("Abonnement et facturation", html)
        self.assertIn("Changer de compte", html)
        self.assertIn("Se déconnecter", html)
        self.assertNotIn("Mes Espaces", html)
        self.assertNotIn("Mon profil et réglages", html)

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
        self.assertNotIn("Abonnement et facturation", html)
