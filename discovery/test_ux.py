from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrencePlace, OccurrencePlaceRole
from geography.models import Place, SpacePlace, SpacePlaceRole
from organizations.models import Organization


User = get_user_model()


class DiscoverySearchUxTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="discovery-ux-owner",
            email="discovery-ux-owner@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="Discovery UX Space",
            slug="discovery-ux-space",
            public_profile=True,
            created_by=self.owner,
        )
        self.public_place = Place.objects.create(
            name="Maison Makolo Lubumbashi",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.664700"),
            longitude=Decimal("27.479400"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        self.private_place = Place.objects.create(
            name="Bureau interne",
            locality="Lubumbashi privé",
            country_code="CD",
            latitude=Decimal("-11.650000"),
            longitude=Decimal("27.490000"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=self.public_place,
            role=SpacePlaceRole.SERVICE_POINT,
            is_public=True,
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=self.private_place,
            role=SpacePlaceRole.OFFICE,
            is_public=False,
        )
        self._activity("Atelier public", self.public_place, 1)
        self._activity(
            "Réunion interne",
            self.private_place,
            2,
            visibility=ActivityVisibility.PRIVATE,
        )

    def _activity(self, title, place, day_offset, *, visibility=ActivityVisibility.PUBLIC):
        activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title=title,
            status=ActivityStatus.PUBLISHED,
            visibility=visibility,
        )
        start_at = timezone.now() + timedelta(days=day_offset)
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
        )
        OccurrencePlace.objects.create(
            occurrence=occurrence,
            place=place,
            role=OccurrencePlaceRole.PRIMARY,
        )

    def test_home_suggests_only_places_exposed_by_public_discovery(self):
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        suggestions = response.context["place_suggestions"]
        self.assertIn("Lubumbashi", suggestions)
        self.assertIn("Maison Makolo Lubumbashi", suggestions)
        self.assertNotIn("Lubumbashi privé", suggestions)
        self.assertNotIn("Bureau interne", suggestions)
        self.assertLessEqual(len(suggestions), 10)

    def test_location_field_keeps_native_fallback_and_visible_label(self):
        response = self.client.get(reverse("discovery:home"))
        self.assertContains(response, '>Lieu</label>')
        self.assertContains(response, 'list="discovery-place-suggestions"')
        self.assertContains(response, '<datalist id="discovery-place-suggestions">')
        self.assertContains(response, "Maison Makolo Lubumbashi")
