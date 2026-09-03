from unittest.mock import patch

from django.test import TestCase

from geography.models import Place

from .intent import ConstraintSource, intent_from_params, resolve_discovery_intent
from .intent_search import search_discovery_intent
from .search import DiscoverySearchResult


class DiscoveryIntentTests(TestCase):
    def setUp(self):
        Place.objects.create(
            name="Agence Makolo Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            is_active=True,
        )

    def test_existing_get_filters_round_trip_without_reinterpretation(self):
        intent = intent_from_params(
            {
                "q": "gospel",
                "place": "Kolwezi",
                "when": "tomorrow",
                "vertical": "event",
                "price": "free",
                "radius_km": "25",
                "ordering": "soon",
            }
        )
        self.assertEqual(intent.text, "gospel")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.vertical, "event")
        self.assertEqual(intent.price, "free")
        self.assertTrue(all(item.source == ConstraintSource.EXPLICIT for item in intent.constraints))
        self.assertEqual(intent.to_search_params()["q"], "gospel")

    def test_natural_transport_request_becomes_visible_constraints(self):
        intent = resolve_discovery_intent({"q": "Je veux voyager à Kolwezi demain matin"})
        self.assertEqual(intent.vertical, "transport")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.period, "morning")
        interpreted = {constraint.key for constraint in intent.constraints if constraint.source == ConstraintSource.INTERPRETED}
        self.assertTrue({"vertical", "place", "when", "period"}.issubset(interpreted))

    def test_unknown_language_remains_classic_text_instead_of_being_invented(self):
        intent = resolve_discovery_intent({"q": "quelque chose de calme avec mes amis"})
        self.assertEqual(intent.text, "quelque chose de calme avec mes amis")
        self.assertEqual(intent.vertical, "")
        self.assertEqual(intent.place, "")
        self.assertEqual(intent.when, "")

    def test_nearby_never_invents_coordinates(self):
        intent = resolve_discovery_intent({"q": "concert autour de moi"})
        self.assertEqual(intent.vertical, "event")
        self.assertEqual(intent.lat, "")
        self.assertEqual(intent.lon, "")
        self.assertEqual(intent.radius_km, "")

    @patch("discovery.intent_search.search_occurrences")
    def test_adapter_passes_day_period_to_canonical_search(self, search_occurrences):
        search_occurrences.return_value = DiscoverySearchResult(
            items=[], timezone_name="Africa/Lubumbashi", total=0, nearby_active=False
        )
        intent = resolve_discovery_intent({"q": "demain matin"})
        search_discovery_intent(intent)
        params = search_occurrences.call_args.args[0]
        self.assertEqual(params["when"], "tomorrow")
        self.assertEqual(params["period"], "morning")
