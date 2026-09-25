from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .console_context import SpaceConsoleContext
from .models import Organization, SpaceArchetype
from .services import create_organization


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
                "name": "Kivu Transit",
                "archetype": SpaceArchetype.TRANSPORT_OPERATOR,
                "description": "Transport régional.",
                "website": "",
                "contact_email": "",
                "contact_phone": "",
                "country": "CD",
                "city": "Lubumbashi",
                "public_profile": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        space = Organization.objects.get(name="Kivu Transit")
        self.assertEqual(space.archetype, SpaceArchetype.TRANSPORT_OPERATOR)

    def test_generic_space_does_not_expose_transport_console(self):
        space = create_organization(
            creator=self.owner,
            name="Collectif générique",
            archetype=SpaceArchetype.GENERIC,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        self.assertIsNotNone(context)
        self.assertNotIn("transport", self._navigation_items(context))

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("organizations:console-transport", kwargs={"slug": space.slug})
        )
        self.assertEqual(response.status_code, 403)

        activities_response = self.client.get(
            reverse("organizations:console-activities", kwargs={"slug": space.slug})
        )
        self.assertEqual(activities_response.status_code, 200)
        self.assertNotContains(activities_response, "Transport / Trajet")
        self.assertNotContains(activities_response, "Transport · Routes · Départs · Véhicules")

    def test_transport_operator_exposes_transport_console(self):
        space = create_organization(
            creator=self.owner,
            name="Kivu Transit",
            archetype=SpaceArchetype.TRANSPORT_OPERATOR,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        items = self._navigation_items(context)
        self.assertIn("transport", items)
        self.assertEqual(items["activities"]["label"], "Services de transport")

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("organizations:console-transport", kwargs={"slug": space.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_creative_space_uses_contextual_navigation_language(self):
        space = create_organization(
            creator=self.owner,
            name="Atelier Kivu",
            archetype=SpaceArchetype.CREATIVE,
        )
        context = SpaceConsoleContext.build(self.owner, space)
        items = self._navigation_items(context)
        self.assertEqual(items["activities"]["label"], "Créations & activités")
        self.assertNotIn("transport", items)