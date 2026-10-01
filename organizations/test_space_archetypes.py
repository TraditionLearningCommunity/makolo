from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .console_context import SpaceConsoleContext
from .models import Organization, SpaceArchetype
from .services import create_organization
from .space_product import operating_preset_for_space


User = get_user_model()


class SpaceArchetypeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="space-archetype-owner",
            email="space-archetype-owner@makolo.test",
            password="SpaceArchetype-2026!",
        )

    def _navigation_items(self, context):
        return {
            item["key"]: item
            for group in context.navigation_groups
            for item in group["items"]
        }

    def test_default_is_generic(self):
        space = Organization.objects.create(
            name="Espace historique",
            created_by=self.owner,
        )
        self.assertEqual(space.archetype, SpaceArchetype.GENERIC)

    def test_creation_form_persists_explicit_archetype(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("organizations:create"),
            {
                "name": "Cabinet Kivu",
                "archetype": SpaceArchetype.SERVICE_PROVIDER,
                "description": "Prestations professionnelles.",
                "website": "",
                "contact_email": "",
                "contact_phone": "",
                "country": "CD",
                "city": "Lubumbashi",
                "public_profile": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        space = Organization.objects.get(name="Cabinet Kivu")
        self.assertEqual(space.archetype, SpaceArchetype.SERVICE_PROVIDER)

    def test_archetype_does_not_gate_transport_vertical(self):
        space = create_organization(
            creator=self.owner,
            name="Collectif générique",
            archetype=SpaceArchetype.GENERIC,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        self.assertIsNotNone(context)
        self.assertIn("transport", self._navigation_items(context))

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("organizations:console-transport", kwargs={"slug": space.slug})
        )
        self.assertEqual(response.status_code, 200)

        activities_response = self.client.get(
            reverse("organizations:console-activities", kwargs={"slug": space.slug})
        )
        self.assertEqual(activities_response.status_code, 200)
        self.assertContains(activities_response, "Transport / Trajet")

    def test_transport_operator_prioritizes_transport_without_exclusivity(self):
        space = create_organization(
            creator=self.owner,
            name="Kivu Transit",
            archetype=SpaceArchetype.TRANSPORT_OPERATOR,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        items = self._navigation_items(context)

        self.assertEqual(context.navigation_groups[0]["label"], "Transport")
        self.assertIn("transport", items)
        self.assertEqual(
            items["activities"]["label"],
            "Services de transport & activités",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("organizations:console-activities", kwargs={"slug": space.slug})
        )
        self.assertContains(response, "Événement")
        self.assertContains(response, "Transport / Trajet")

    def test_service_provider_uses_contextual_navigation_language(self):
        space = create_organization(
            creator=self.owner,
            name="Cabinet Kivu",
            archetype=SpaceArchetype.SERVICE_PROVIDER,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        items = self._navigation_items(context)

        self.assertEqual(context.navigation_groups[0]["label"], "Prestations")
        self.assertEqual(items["activities"]["label"], "Prestations & activités")
        self.assertIn("transport", items)

    def test_operating_profiles_cover_initial_short_taxonomy(self):
        self.assertEqual(
            {value for value, _label in SpaceArchetype.choices},
            {
                "generic",
                "creative",
                "media",
                "education",
                "commerce",
                "service_provider",
                "transport_operator",
                "community",
            },
        )
        commerce = Organization(
            name="Commerce",
            created_by=self.owner,
            archetype=SpaceArchetype.COMMERCE,
        )
        preset = operating_preset_for_space(commerce)
        self.assertEqual(preset.suggested_verticals[0], "obtention")
        self.assertIn("crm", preset.featured_modules)
