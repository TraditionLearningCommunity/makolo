from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import TestCase

from geography.models import Place

from .intent import ConstraintSource, resolve_discovery_intent
from .search import resolve_time_window


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

    def test_classic_single_signal_query_keeps_legacy_text_semantics(self):
        intent = resolve_discovery_intent({"q": "concert"})
        self.assertEqual(intent.text, "concert")
        self.assertEqual(intent.vertical, "")
        self.assertEqual(intent.constraints, ())

    def test_natural_transport_query_becomes_structured_intent(self):
        intent = resolve_discovery_intent({"q": "Je veux voyager à Kolwezi demain matin"})
        self.assertEqual(intent.vertical, "transport")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.period, "morning")
        self.assertEqual(intent.text, "")
        self.assertTrue(intent.constraints)
        self.assertTrue(all(item.source == ConstraintSource.INTERPRETED for item in intent.constraints))
        self.assertEqual(
            intent.to_search_params(),
            {
                "place": "Kolwezi",
                "when": "tomorrow",
                "period": "morning",
                "vertical": "transport",
            },
        )

    def test_unresolved_domain_words_remain_search_text(self):
        intent = resolve_discovery_intent({"q": "concert gospel à Kolwezi demain"})
        self.assertEqual(intent.vertical, "event")
        self.assertEqual(intent.place, "Kolwezi")
        self.assertEqual(intent.when, "tomorrow")
        self.assertEqual(intent.text.casefold(), "gospel")

    def test_explicit_filters_remain_explicit_and_are_not_overridden(self):
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
