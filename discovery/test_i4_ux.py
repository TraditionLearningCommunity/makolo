from django.test import TestCase
from django.urls import reverse

from geography.models import Place

from .intent import resolve_discovery_intent
from .templatetags.discovery_query import discovery_without


class Discover2027UxTests(TestCase):
    def setUp(self):
        Place.objects.create(
            name="Agence Makolo Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            is_active=True,
        )

    def test_discover_home_is_intent_first_but_keeps_advanced_filters(self):
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Je veux voyager à Kolwezi demain matin")
        self.assertContains(response, "Choisir :")
        self.assertContains(response, "Autour de moi")
        self.assertContains(response, "Ce soir")
        self.assertContains(response, "Filtres")
        self.assertContains(response, 'name="period"', html=False)
        self.assertContains(response, 'name="date_from"', html=False)
        self.assertContains(response, 'name="date_to"', html=False)

    def test_natural_intent_is_rendered_as_visible_constraints(self):
        response = self.client.get(
            reverse("discovery:home"),
            {"q": "Je veux voyager à Kolwezi demain matin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compris :")
        self.assertContains(response, "Voyager")
        self.assertContains(response, "Kolwezi")
        self.assertContains(response, "Demain")
        self.assertContains(response, "Matin")
        keys = {constraint.key for constraint in response.context["applied_constraints"]}
        self.assertEqual(keys, {"vertical", "place", "when", "period"})

    def test_removing_interpreted_constraint_rebuilds_structured_query(self):
        intent = resolve_discovery_intent({"q": "Je veux voyager à Kolwezi demain matin"})
        query = discovery_without(intent, "place")
        self.assertNotIn("place=", query)
        self.assertIn("vertical=transport", query)
        self.assertIn("when=tomorrow", query)
        self.assertIn("period=morning", query)
        self.assertNotIn("Je+veux", query)

    def test_nearby_removal_drops_coordinates_and_proximity_ordering(self):
        intent = resolve_discovery_intent(
            {
                "q": "concert demain",
                "lat": "-11.6647",
                "lon": "27.4794",
                "radius_km": "10",
                "ordering": "proximity",
            }
        )
        query = discovery_without(intent, "nearby")
        self.assertNotIn("lat=", query)
        self.assertNotIn("lon=", query)
        self.assertNotIn("radius_km=", query)
        self.assertNotIn("ordering=", query)
