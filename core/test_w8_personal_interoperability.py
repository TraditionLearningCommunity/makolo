from django.test import RequestFactory, SimpleTestCase, TestCase
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
        self.assertContains(response, "Services à découvrir")
        self.assertContains(response, "Mes connexions")
        self.assertContains(response, "Tavily")
        self.assertNotContains(response, "Marketplace")
        self.assertNotContains(response, "dans cet environnement")
        self.assertNotContains(response, "Explorez les services disponibles pour commencer")
        self.assertNotContains(response, "Notifications sur mes appareils")
        self.assertNotContains(response, "Paiement de démonstration")
        self.assertNotContains(response, "Connecter")
        self.assertNotContains(response, "Gmail")
        self.assertNotContains(response, "Google Calendar")
        self.assertContains(response, "OpenAI API")

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
        url = reverse("core:participant-connections")
        response = self.client.get(f"{url}?tab=mine")
        detail = self.client.get(f"{url}?connection={own.pk}")
        html = detail.content.decode("utf-8")

        self.assertContains(response, "Service personnel")
        self.assertContains(response, "Connecté et disponible")
        self.assertContains(detail, "Génération de texte")
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
        self.assertNotContains(response, "Extension déclarée")
        self.assertNotContains(response, "Mode démonstration uniquement")

    def test_real_discovery_handoff_only_for_usable_personal_research_connection(self):
        own = self._connection(
            name="Recherche utilisable",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
        )
        own.routes.update(capability=IntelligenceCapability.WEB_RESEARCH.value)
        other = self._connection(
            name="Recherche désactivée",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
            enabled=False,
        )
        other.routes.update(capability=IntelligenceCapability.WEB_RESEARCH.value)
        foreign = self._connection(
            name="Recherche autre Profil",
            scope=ProviderScope.PROFILE,
            profile=self.other_profile,
        )
        foreign.routes.update(capability=IntelligenceCapability.WEB_RESEARCH.value)
        self.client.force_login(self.user)
        url = reverse("core:participant-connections")
        response = self.client.get(f"{url}?tab=mine")
        detail = self.client.get(f"{url}?connection={own.pk}")
        disabled = self.client.get(f"{url}?connection={other.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recherche utilisable")
        self.assertContains(response, "Recherche désactivée")
        self.assertNotContains(response, "Recherche autre Profil")
        self.assertContains(detail, "Explorer dans Découvrir", count=1)
        self.assertContains(detail, reverse("discovery:home"))
        self.assertNotContains(disabled, "Explorer dans Découvrir")

    def test_catalogue_filters_and_n3_use_owner_offers_only(self):
        from unittest.mock import patch

        self.client.force_login(self.user)
        url = reverse("core:participant-connections")
        response = self.client.get(f"{url}?tab=discover&cap=web_research&q=Tavily")
        self.assertContains(response, "Tavily")
        self.assertNotContains(response, "Exa")
        self.assertNotContains(response, "OpenAI API")

        with patch.dict(
            "os.environ",
            {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "test-key-for-display-only"},
        ):
            detail = self.client.get(f"{url}?offer=tavily")
            self.assertContains(detail, 'name="provider" value="tavily"')
            self.assertContains(detail, 'name="api_key"')
            self.assertContains(detail, 'name="consent"')
            self.assertNotContains(detail, 'name="model"')

        unknown = self.client.get(f"{url}?offer=unregistered-provider")
        self.assertNotContains(unknown, 'name="provider" value="unregistered-provider"')

    def test_foreign_connection_cannot_be_opened_via_n3_query(self):
        own = self._connection(
            name="Ma connexion contrôlée",
            scope=ProviderScope.PROFILE,
            profile=self.profile,
        )
        foreign = self._connection(
            name="Connexion d'un autre profil",
            scope=ProviderScope.PROFILE,
            profile=self.other_profile,
        )
        self.client.force_login(self.user)
        url = reverse("core:participant-connections")
        detail = self.client.get(f"{url}?connection={own.pk}")
        self.assertContains(detail, "Ma connexion contrôlée")
        foreign_detail = self.client.get(f"{url}?connection={foreign.pk}")
        self.assertNotContains(foreign_detail, "Connexion d'un autre profil")
        self.assertNotContains(foreign_detail, str(foreign.pk))

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


class C2InteroperabilityPresentationContractTests(SimpleTestCase):
    def test_connection_with_no_active_capability_is_not_described_as_usable(self):
        from interoperability.presentation import connection_status_label

        self.assertEqual(
            connection_status_label(
                {
                    "enabled": True,
                    "connected": True,
                    "usable": False,
                    "health": "healthy",
                    "capabilities": [],
                }
            ),
            "Connecté · aucun usage disponible",
        )

    def test_c3_explanations_do_not_grant_authority(self):
        from interoperability.presentation import present_connection

        base = {
            "display_name": "Profil service",
            "connected": True,
            "enabled": True,
            "status": "connected",
            "health": "healthy",
            "usable": False,
            "capabilities": [],
        }
        no_capability = present_connection(base)
        self.assertEqual(no_capability["experience_state"], "no_capability")
        self.assertEqual(
            no_capability["experience_message"],
            "Aucun usage disponible pour cette connexion.",
        )
        self.assertNotIn("execute_url", no_capability)
        self.assertNotIn("connect_url", no_capability)
        disabled = present_connection({**base, "enabled": False, "usable": True})
        self.assertEqual(disabled["experience_state"], "disabled")
        unavailable = present_connection({**base, "health": "unavailable"})
        self.assertEqual(unavailable["experience_state"], "unavailable")
        usable = present_connection({
            **base, "usable": True, "capabilities": ["text_generate"],
        })
        self.assertEqual(usable["experience_state"], "usable")
        self.assertEqual(
            usable["experience_message"], "Ce service est prêt à être utilisé."
        )
        self.assertNotIn("execute_url", usable)

    def test_action_metadata_does_not_promise_an_execution_link(self):
        from interoperability.presentation import present_action

        row = present_action(
            {
                "code": "notifications.send",
                "available": True,
                "authorized": True,
                "requires_connection": False,
            }
        )
        self.assertEqual(row["status_label"], "Capacité disponible dans Makolo")
        self.assertNotIn("execute_url", row)
        self.assertNotIn("connect_url", row)
