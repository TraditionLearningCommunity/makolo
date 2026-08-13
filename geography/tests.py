import importlib
from decimal import Decimal

from django.apps import apps
from django.test import TestCase
from events.models import EventVenue, VenueKind

from .test_models import *
from .test_permissions import *


class EventVenueBackfillTests(TestCase):
    def test_backfill_keeps_distinct_venues_and_skips_online(self):
        physical = EventVenue.objects.create(name="Salle commune", kind=VenueKind.PHYSICAL, address="1 rue", city="Lubumbashi", country="RDC", latitude=Decimal("-11.664"), longitude=Decimal("27.479"))
        same_name = EventVenue.objects.create(name="Salle commune", kind=VenueKind.PHYSICAL, address="1 rue", city="Lubumbashi", country="RDC")
        hybrid = EventVenue.objects.create(name="Hybride", kind=VenueKind.HYBRID, city="Nairobi", country="Kenya")
        online = EventVenue.objects.create(name="En ligne", kind=VenueKind.ONLINE)
        migration = importlib.import_module("events.migrations.0003_eventvenue_place")
        migration.backfill_event_venue_places(apps, None)
        for venue in (physical, same_name, hybrid, online):
            venue.refresh_from_db()
        self.assertIsNotNone(physical.place_id)
        self.assertIsNotNone(same_name.place_id)
        self.assertNotEqual(physical.place_id, same_name.place_id)
        self.assertEqual(physical.place.country_code, "CD")
        self.assertEqual(hybrid.place.country_code, "KE")
        self.assertIsNone(online.place_id)
