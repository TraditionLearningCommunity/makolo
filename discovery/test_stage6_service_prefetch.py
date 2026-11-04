"""Stage 6: Service Discovery preloads vertical relations without changing admission."""
from django.test import SimpleTestCase

from discovery.unified import _service_discovery_queryset


class DiscoveryServiceVerticalPreloadTests(SimpleTestCase):
    def test_service_candidates_preload_verticals(self):
        relations = _service_discovery_queryset().query.select_related
        activity = relations["activity"]
        for name in (
            "event_vertical",
            "transport_service",
            "funding_details",
            "obtention_details",
        ):
            with self.subTest(relation=name):
                self.assertIn(name, activity)
