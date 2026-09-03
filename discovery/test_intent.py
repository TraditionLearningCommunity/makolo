from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import UserProfile
from geography.models import Place
from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceResult

from .intelligence import interpret_with_intelligence
from .intent import ConstraintSource, intent_from_params, resolve_discovery_intent
from .intent_search import search_discovery_intent
from .search import DiscoverySearchResult, resolve_time_window


LUB = ZoneInfo("Africa/Lubumbashi")


class DiscoveryIntentTests(TestCase):
    def setUp(self):
        Place.objects.create(
            name="Agence Makolo Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            is_active=True,
        )
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=LUB)

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

    def test_classic_single_signal_query_keeps_legacy_text_semantics(self):
        intent = resolve_discovery_intent({"q": "concert"})
        self.assertEqual(intent.text, "concert")
        self.assertEqual(intent.vertical, "")
        self.assertEqual(intent.constraints, ())

    def test_natural_transport_request_becomes_visible_constraints(self):
        intent = resolve_discovery_intent({"q": "Je veux voyager à Kolwezi demain matin"})
        self.assertEqual(intent.vertical, "transport")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.period, "morning")
        self.assertEqual(intent.text, "")
        interpreted = {
            constraint.key
            for constraint in intent.constraints
            if constraint.source == ConstraintSource.INTERPRETED
        }
        self.assertTrue({"vertical", "place", "when", "period"}.issubset(interpreted))
        self.assertEqual(
            intent.to_search_params(),
            {
                "place": "Kolwezi",
                "when": "tomorrow",
                "period": "morning",
                "vertical": "transport",
            },
        )

    def test_unresolved_domain_words_remain_classic_search_text(self):
        intent = resolve_discovery_intent({"q": "concert gospel à Kolwezi demain"})
        self.assertEqual(intent.vertical, "event")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.text.casefold(), "gospel")

    def test_unknown_language_remains_classic_text_instead_of_being_invented(self):
        intent = resolve_discovery_intent({"q": "quelque chose de calme avec mes amis"})
        self.assertEqual(intent.text, "quelque chose de calme avec mes amis")
        self.assertEqual(intent.vertical, "")
        self.assertEqual(intent.place, "")
        self.assertEqual(intent.when, "")

    def test_nearby_without_coordinates_does_not_invent_location(self):
        intent = resolve_discovery_intent({"q": "concert autour de moi"})
        self.assertEqual(intent.text, "concert autour de moi")
        self.assertEqual(intent.vertical, "")
        self.assertEqual(intent.lat, "")
        self.assertEqual(intent.lon, "")
        self.assertEqual(intent.radius_km, "")

    def test_explicit_filters_are_not_overridden_by_text(self):
        intent = resolve_discovery_intent(
            {
                "q": "gospel",
                "vertical": "event",
                "place": "Kolwezi",
                "when": "tomorrow",
                "period": "evening",
            }
        )
        self.assertEqual(intent.text, "gospel")
        self.assertEqual(intent.vertical, "event")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.period, "evening")
        sources = {item.key: item.source for item in intent.constraints}
        self.assertEqual(sources["vertical"], ConstraintSource.EXPLICIT)
        self.assertEqual(sources["place"], ConstraintSource.EXPLICIT)
        self.assertEqual(sources["when"], ConstraintSource.EXPLICIT)
        self.assertEqual(sources["period"], ConstraintSource.EXPLICIT)

    def test_morning_refines_tomorrow_to_single_local_period(self):
        start, end = resolve_time_window(
            {"when": "tomorrow", "period": "morning"},
            zone=LUB,
            now=self.now,
        )
        self.assertEqual(start, datetime(2026, 8, 21, 5, 0, tzinfo=LUB))
        self.assertEqual(end, datetime(2026, 8, 21, 12, 0, tzinfo=LUB))

    def test_period_without_single_day_is_rejected(self):
        with self.assertRaises(ValidationError):
            resolve_time_window({"period": "morning"}, zone=LUB, now=self.now)
        with self.assertRaises(ValidationError):
            resolve_time_window({"when": "weekend", "period": "morning"}, zone=LUB, now=self.now)

    def test_invalid_period_is_rejected(self):
        with self.assertRaises(ValidationError):
            resolve_time_window({"when": "tomorrow", "period": "night"}, zone=LUB, now=self.now)

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

    def test_intelligence_accepts_only_validated_canonical_constraints(self):
        intent = resolve_discovery_intent({"q": "une sortie calme demain à Kolwezi"})
        gateway = Mock()
        gateway.execute.return_value = IntelligenceResult(
            available=True,
            output={
                "vertical": "event",
                "place": "Kolwezi",
                "when": "tomorrow",
                "period": "evening",
                "price": "",
                "text": "calme",
            },
        )
        resolved = interpret_with_intelligence(intent, gateway=gateway)
        self.assertEqual(resolved.vertical, "event")
        self.assertEqual(resolved.place, "Kolwezi")
        self.assertEqual(resolved.when, "tomorrow")
        self.assertEqual(resolved.period, "evening")
        self.assertEqual(resolved.text, "calme")
        self.assertTrue(all(item.source == ConstraintSource.INTERPRETED for item in resolved.constraints))

    def test_intelligence_rejects_invented_place_and_falls_back(self):
        intent = resolve_discovery_intent({"q": "une sortie à Atlantis demain"})
        gateway = Mock()
        gateway.execute.return_value = IntelligenceResult(
            available=True,
            output={"vertical": "event", "place": "Atlantis", "when": "tomorrow", "text": ""},
        )
        resolved = interpret_with_intelligence(intent, gateway=gateway)
        self.assertEqual(resolved, intent)

    def test_intelligence_rejects_ambiguous_period_and_falls_back(self):
        intent = resolve_discovery_intent({"q": "quelque chose le week-end matin"})
        gateway = Mock()
        gateway.execute.return_value = IntelligenceResult(
            available=True,
            output={"vertical": "event", "when": "weekend", "period": "morning", "text": ""},
        )
        resolved = interpret_with_intelligence(intent, gateway=gateway)
        self.assertEqual(resolved, intent)

    def test_intelligence_cannot_override_deterministic_constraint(self):
        intent = resolve_discovery_intent({"q": "concert gospel à Kolwezi demain"})
        gateway = Mock()
        gateway.execute.return_value = IntelligenceResult(
            available=True,
            output={"vertical": "transport", "place": "Kolwezi", "when": "tomorrow", "text": "gospel"},
        )
        resolved = interpret_with_intelligence(intent, gateway=gateway)
        self.assertEqual(resolved, intent)

    def test_deterministic_intent_never_calls_intelligence(self):
        intent = resolve_discovery_intent({"q": "Je veux voyager à Kolwezi demain matin"})
        gateway = Mock()
        resolved = interpret_with_intelligence(intent, gateway=gateway)
        self.assertEqual(resolved, intent)
        gateway.execute.assert_not_called()

    @patch("discovery.intelligence.IntelligenceGateway")
    @patch("discovery.intelligence.build_runtime_registry")
    def test_authenticated_user_is_resolved_to_user_profile_for_runtime_scope(self, build_registry, gateway_class):
        user = get_user_model().objects.create_user(username="intent-profile", password="unused")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        build_registry.return_value = Mock()
        gateway_class.return_value.execute.return_value = IntelligenceResult.unavailable()
        intent = resolve_discovery_intent({"q": "quelque chose de calme avec mes amis"})

        resolved = interpret_with_intelligence(intent, profile=user)

        self.assertEqual(resolved, intent)
        build_registry.assert_called_once_with(
            capability=IntelligenceCapability.STRUCTURED_GENERATE,
            profile=profile,
        )
