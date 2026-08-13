from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .distance import haversine_distance_meters
from .models import Place, Zone, ZoneType
from .selectors import distance_between_places, nearby_places, places_in_bounding_box, places_in_country, places_in_locality
from .value_objects import GeoPoint


class PlaceModelTests(TestCase):
    def test_place_accepts_missing_or_valid_coordinate_pair(self):
        plain = Place.objects.create(name="Bureau sans GPS", locality="Lubumbashi", country_code="cd")
        self.assertIsNone(plain.point)
        self.assertEqual(plain.country_code, "CD")
        located = Place.objects.create(name="Point", latitude=Decimal("-11.664"), longitude=Decimal("27.479"), timezone="Africa/Lubumbashi")
        self.assertAlmostEqual(located.point.latitude, -11.664)

    def test_place_rejects_invalid_and_partial_coordinates(self):
        with self.assertRaises(ValidationError):
            Place(name="Latitude invalide", latitude=Decimal("91"), longitude=Decimal("0")).full_clean()
        with self.assertRaises(ValidationError):
            Place(name="Longitude invalide", latitude=Decimal("0"), longitude=Decimal("181")).full_clean()
        with self.assertRaises(ValidationError):
            Place(name="Partiel", latitude=Decimal("1")).full_clean()

    def test_database_constraints_reject_invalid_coordinates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Place.objects.bulk_create([Place(name="DB latitude", latitude=Decimal("91"), longitude=Decimal("0"))])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Place.objects.bulk_create([Place(name="DB partiel", latitude=Decimal("1"), longitude=None)])

    def test_timezone_and_country_code_validation(self):
        with self.assertRaises(ValidationError):
            Place(name="Timezone invalide", timezone="Mars/Lubumbashi").full_clean()
        place = Place.objects.create(name="Pays", country_code="ke")
        self.assertEqual(place.country_code, "KE")
        with self.assertRaises(ValidationError):
            Place(name="Pays invalide", country_code="KEN").full_clean()


class ZoneModelTests(TestCase):
    def test_administrative_and_radius_zones(self):
        Zone.objects.create(name="Ville de Lubumbashi", zone_type=ZoneType.ADMINISTRATIVE, locality="Lubumbashi", country_code="CD")
        center = Place.objects.create(name="Centre", latitude=Decimal("-11.664"), longitude=Decimal("27.479"))
        radius = Zone.objects.create(name="Centre + 5 km", zone_type=ZoneType.RADIUS, center_place=center, radius_m=5000)
        self.assertEqual(radius.radius_m, 5000)

    def test_radius_requires_located_center_and_positive_radius(self):
        with self.assertRaises(ValidationError):
            Zone(name="Sans centre", zone_type=ZoneType.RADIUS, radius_m=1000).full_clean()
        center = Place.objects.create(name="Sans GPS")
        with self.assertRaises(ValidationError):
            Zone(name="Centre sans GPS", zone_type=ZoneType.RADIUS, center_place=center, radius_m=1000).full_clean()
        located = Place.objects.create(name="GPS", latitude=0, longitude=0)
        with self.assertRaises(ValidationError):
            Zone(name="Rayon nul", zone_type=ZoneType.RADIUS, center_place=located, radius_m=0).full_clean()


class DistanceAndSelectorTests(TestCase):
    def test_distance_contract_and_nearby_order(self):
        origin = GeoPoint(0, 0)
        near = GeoPoint(0, 0.01)
        far = GeoPoint(0, 0.02)
        self.assertAlmostEqual(haversine_distance_meters(origin, origin), 0, places=6)
        self.assertAlmostEqual(haversine_distance_meters(origin, near), haversine_distance_meters(near, origin), places=6)
        self.assertGreater(haversine_distance_meters(origin, near), 0)
        self.assertLess(haversine_distance_meters(origin, near), haversine_distance_meters(origin, far))
        first = Place.objects.create(name="Proche", locality="Testville", country_code="CD", latitude=0, longitude=Decimal("0.01"))
        second = Place.objects.create(name="Loin", locality="Testville", country_code="CD", latitude=0, longitude=Decimal("0.02"))
        self.assertEqual([item[0] for item in nearby_places(origin, radius_m=3000)], [first, second])

    def test_filters_and_missing_coordinates(self):
        inside = Place.objects.create(name="Dedans", locality="Lubumbashi", country_code="CD", latitude=Decimal("-11.66"), longitude=Decimal("27.48"))
        Place.objects.create(name="Ailleurs", locality="Nairobi", country_code="KE", latitude=Decimal("-1.28"), longitude=Decimal("36.82"))
        missing = Place.objects.create(name="Sans GPS", locality="Lubumbashi", country_code="CD")
        self.assertIn(inside, places_in_locality("lubumbashi"))
        self.assertEqual(places_in_country("cd").count(), 2)
        self.assertEqual(list(places_in_bounding_box(south=-12, west=27, north=-11, east=28)), [inside])
        self.assertIsNone(distance_between_places(inside, missing))
