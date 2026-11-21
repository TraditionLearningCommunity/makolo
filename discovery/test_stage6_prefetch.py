"""Focused regression for stage 6 Discovery bulk vertical relationship loading."""
from django.test import SimpleTestCase
from django.utils import timezone

from discovery.search import _base_queryset


class DiscoveryVerticalPrefetchTests(SimpleTestCase):
    def test_occurrence_search_preloads_all_vertical_relations(self):
        # Building the queryset is read-only: no fixtures or database access.
        related = _base_queryset(now=timezone.now()).query.select_related
        activity = related["activity"]
        for relation in (
            "event_vertical",
            "service_details",
            "transport_service",
            "funding_details",
            "obtention_details",
        ):
            with self.subTest(relation=relation):
                self.assertIn(relation, activity)
