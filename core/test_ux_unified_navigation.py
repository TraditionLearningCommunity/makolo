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

    def test_personal_navigation_keeps_mature_action_surfaces_primary(self):
        html = render_to_string(
            "partials/navigation_links.html",
            {"request": self._request(), "space_console": None},
        )

        for label in ("Accueil", "Mes démarches", "Conversations", "Profil"):
            self.assertIn(f"<span>{label}</span>", html)
        for label in ("Mes Espaces", "Mes accès", "Bibliothèque", "Mes veilles", "Historique"):
            self.assertIn(f"<span>{label}</span>", html)
        self.assertNotIn("<span>Découvrir</span>", html)
        self.assertNotIn(">Services<", html)
        self.assertNotIn(">Opportunités<", html)
        self.assertNotIn(">Abonnement<", html)

    def test_discover_stays_distinct_and_accessible_from_anchored_sidebar_cta(self):
        request = self._request()
        sidebar_html = render_to_string(
            "partials/sidebar.html",
            {"request": request, "space_console": None},
        )
        navigation_html = render_to_string(
            "partials/navigation_links.html",
            {"request": request, "space_console": None},
        )

        discover_href = f'href="{reverse("discovery:home")}"'
        self.assertEqual(navigation_html.count(discover_href), 0)
        self.assertEqual(sidebar_html.count(discover_href), 1)
        self.assertIn("Trouver une prochaine possibilité", sidebar_html)
        self.assertIn("Découvrir", sidebar_html)

    def test_conversations_and_profile_expose_current_page_state(self):
        conversations_html = render_to_string(
            "partials/navigation_links.html",
            {"request": self._request("conversations:list"), "space_console": None},
        )
        profile_html = render_to_string(
            "partials/navigation_links.html",
            {"request": self._request("account:profile"), "space_console": None},
        )

        self.assertIn('href="{}" class="mk-nav-item is-active" aria-current="page"'.format(reverse("conversations:list")), conversations_html)
        self.assertIn('href="{}" class="mk-nav-item is-active" aria-current="page"'.format(reverse("account:profile")), profile_html)

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
