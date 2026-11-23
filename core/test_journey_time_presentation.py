"""N3 calendar labels come only from the owner's Occurrence calendar."""

from datetime import date, datetime, timezone as utc
from types import SimpleNamespace

from django.test import SimpleTestCase

from core.journey_time_presentation import additional_place_details, journey_day_label


class JourneyN3CalendarPresentationTests(SimpleTestCase):
    def test_lubumbashi_event_day_and_distant_markers(self):
        occurrence = SimpleNamespace(start_date=date(2026, 12, 11), timezone="Africa/Lubumbashi")
        cases = [
            (datetime(2026, 4, 10, 12, tzinfo=utc.utc), "Jour −245"),
            (datetime(2026, 11, 25, 12, tzinfo=utc.utc), "Jour −16"),
            (datetime(2026, 12, 9, 12, tzinfo=utc.utc), "Jour −2"),
            (datetime(2026, 12, 11, 12, tzinfo=utc.utc), "Jour J"),
            (datetime(2026, 12, 13, 12, tzinfo=utc.utc), "Jour J +2"),
            (datetime(2027, 6, 5, 12, tzinfo=utc.utc), "Jour J +176"),
        ]
        for moment, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(journey_day_label(occurrence, at=moment), expected)

    def test_timezone_boundary_is_not_utc_midnight(self):
        moment = datetime(2026, 12, 10, 22, 30, tzinfo=utc.utc)
        event = SimpleNamespace(start_date=date(2026, 12, 11), timezone="Africa/Lubumbashi")
        self.assertEqual(journey_day_label(event, at=moment), "Jour J")
        elsewhere = SimpleNamespace(start_date=date(2026, 12, 11), timezone="America/New_York")
        self.assertEqual(journey_day_label(elsewhere, at=moment), "Jour −1")

    def test_missing_owner_day_or_timezone_does_not_invent_jour_j(self):
        self.assertIsNone(journey_day_label(None))
        self.assertIsNone(journey_day_label(SimpleNamespace(start_date=None, timezone="Africa/Lubumbashi")))
        self.assertIsNone(
            journey_day_label(SimpleNamespace(start_date=date(2026, 12, 11), timezone="Invalid/Zone"))
        )

    def test_primary_place_is_not_repeated(self):
        same = SimpleNamespace(name="Lubumbashi", locality="Lubumbashi", address_line="")
        self.assertIsNone(additional_place_details(same))
        detailed = SimpleNamespace(
            name="Centre de conférence",
            locality="Lubumbashi",
            address_line="Avenue centrale",
        )
        self.assertEqual(additional_place_details(detailed), "Avenue centrale · Lubumbashi")
