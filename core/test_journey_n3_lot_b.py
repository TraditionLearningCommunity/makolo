"""Journey N3 Lot B — owner-sourced practical facts, never inferred dates."""

from datetime import date
from types import SimpleNamespace
from uuid import UUID

from django.test import SimpleTestCase

from core.api.detail_projections import _occurrence_ref


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class JourneyN3PracticalFactsTests(SimpleTestCase):
    def _occurrence(self, links):
        return SimpleNamespace(
            pk=UUID("00000000-0000-0000-0000-000000000005"),
            label="Conférence",
            status="scheduled",
            timing_kind="date_only",
            start_date=date(2026, 12, 11),
            start_time=None,
            end_date=None,
            end_time=None,
            start_at=None,
            end_at=None,
            timezone="Africa/Lubumbashi",
            place_links=_Rows(links),
        )

    def test_place_uses_occurrence_owner_relation(self):
        place = SimpleNamespace(
            name="Centre de conférence",
            address_line="Avenue centrale",
            locality="Lubumbashi",
            access_instructions="Entrée principale",
        )
        result = _occurrence_ref(
            self._occurrence([SimpleNamespace(role="primary", place=place)])
        )
        self.assertEqual(result["place"]["name"], "Centre de conférence")
        self.assertEqual(result["place"]["locality"], "Lubumbashi")
        self.assertEqual(result["timing"]["start_date"], "2026-12-11")
        self.assertIsNone(result["timing"]["start_at"])
        self.assertIsNone(result["timing"]["start_time"])

    def test_no_place_remains_absent(self):
        result = _occurrence_ref(self._occurrence([]))
        self.assertIsNone(result["place"])
        self.assertIsNone(result["timing"]["start_at"])
