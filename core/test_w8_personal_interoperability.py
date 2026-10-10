from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from accounts.models import User, UserProfile
from intelligence.capabilities import IntelligenceCapability
from intelligence.models import (
    IntelligenceRoute,
    ProviderConnection,
    ProviderCredential,
    ProviderHealth,
    ProviderProtocol,
    ProviderScope,
)
from organizations.models import Organization

from .personal_navigation import personal_surface_owner


class W8PersonalConnectionsWebTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="w8-profile",
            email="w8-profile@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="w8-other",
            email="w8-other@example.test",
            password="StrongPass2026!",
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.other_profile = UserProfile.objects.create(user=self.other)

    def _connection(
        self,
        *,
        name,
        scope,
        profile=None,
        space=None,
        enabled=True,
        health=ProviderHealth.HEALTHY,
    ):
        connection = ProviderConnection.objects.create(
            name=name,
            protocol=ProviderProtocol.OPENAI_COMPATIBLE,
            base_url="https://provider.example.test/v1",
            default_model="test-model",
            scope=scope,
            profile=profile,
            space=space,
            enabled=enabled,
            health_status=health,
        )
        IntelligenceRoute.objects.create(
            connection=connection,
            capability=IntelligenceCapability.TEXT_GENERATE.value,
            enabled=True,
        )
        return connection

    def test_avatar_exposes_connections_only_for_authenticated_personal_shell(self):
        connections_url = reverse("core:participant-connections")

        anonymous = self.client.get(reverse("core:home"))
        self.assertNotContains(anonymous, connections_url)

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, connections_url)
        self.assertContains(response, ">Connexions<")

    def test_connections_route_is_protected_and_owned_by_moi(self):
        url = reverse("core:participant-connections")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])

        request = RequestFactory().get(url)
        request.user = self.user
        request.resolver_match = resolve(url)
        surface = personal_surface_owner(request)
        self.assertEqual(surface.owner, "me")
        self.assertEqual(surface.title, "Connexions")
        self.assertFalse(surface.is_primary)

    def test_empty_state_is_clean_and_does_not_invent_providers(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-connections"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, "Aucune connexion pour le moment.")
        self.assertContains(
            response,
            "Aucun service n’est encore disponible pour votre Profil.",
        )
        self.assertNotContains(response, "Marketplace")
        self.assertNotContains(response, "Connecter")
        self.assertNotContains(response, "Gmail")
        self.assertNotContains(response, "Google Calendar")
        self.assertNotContains(response, "OpenAI")

    def test_profile_connections_are_humanized_and_secret_free(self):
        own = self._connection(
            name="Service personnel",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
        )
        other = self._connection(
            name="Autre service",
            scope=ProviderScope.PROFILE,
            profile=self.other_profile,
        )
        self._connection(
            name="Service désactivé",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
            enabled=False,
        )
        self._connection(
            name="Service dégradé",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
            health=ProviderHealth.DEGRADED,
        )
        self._connection(
            name="Service indisponible",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
            health=ProviderHealth.UNAVAILABLE,
        )
        ProviderCredential.objects.create(
            connection=own,
            encrypted_secret="w8-secret-ciphertext",
            key_hint="w8-key-hint",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-connections"))
        html = response.content.decode("utf-8")

        self.assertContains(response, "Service personnel")
        self.assertContains(response, "Connecté et disponible")
        self.assertContains(response, "Génération de texte")
        self.assertContains(response, "Service désactivé")
        self.assertContains(response, "Désactivé")
        self.assertContains(response, "Service dégradé")
        self.assertContains(response, "Connecté · disponibilité réduite")
        self.assertContains(response, "Service indisponible")
        self.assertContains(response, "Momentanément indisponible")
        self.assertNotContains(response, "utilisable par Makolo")
        self.assertNotContains(response, "Gestion disponible")
        self.assertNotContains(response, "Déconnecter")
        self.assertNotContains(response, "Reconnecter")
        self.assertNotContains(response, "Autre service")
        self.assertNotIn(str(other.pk), html)
        self.assertNotIn("w8-secret-ciphertext", html)
        self.assertNotIn("w8-key-hint", html)
        self.assertNotIn("provider.example.test", html)
        self.assertNotIn("test-model", html)
        self.assertNotIn("openai_compatible", html)
        self.assertNotIn("text_generate", html)

    def test_space_and_platform_connections_never_leak_into_personal_page(self):
        space = Organization.objects.create(
            name="W8 Space",
            slug="w8-space",
            created_by=self.user,
        )
        self._connection(
            name="Connexion Espace privée",
            scope=ProviderScope.SPACE,
            space=space,
        )
        self._connection(
            name="Connexion Platform privée",
            scope=ProviderScope.PLATFORM,
        )
        self._connection(
            name="Ma connexion",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-connections"))

        self.assertContains(response, "Ma connexion")
        self.assertNotContains(response, "Connexion Espace privée")
        self.assertNotContains(response, "Connexion Platform privée")

    def test_personal_primary_navigation_remains_five_destinations(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-connections"))
        html = response.content.decode("utf-8")
        mobile = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]

        for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
            self.assertIn(f"<span>{label}</span>", mobile)
        self.assertNotIn(">Connexions<", mobile)
