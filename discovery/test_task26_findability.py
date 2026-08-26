from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from activities.models import (
    ActivityStatus,
    ActivityVisibility,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from activities.services import create_activity, create_occurrence
from capacity.models import CapacityReservation
from commerce.models import CommerceOrder
from events.models import Event
from geography.models import Place
from journeys.models import ExternalBeneficiary, Journey, JourneyStatus, WorkflowKind
from payments.models import Payment

from .models import ActivityBookmark
from .search import search_occurrences


User = get_user_model()


class Task26FindabilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="t26-owner",
            email="t26-owner@example.test",
            password="StrongPass2026!",
        )
        self.participant = User.objects.create_user(
            username="t26-participant",
            email="t26-participant@example.test",
            password="StrongPass2026!",
        )
        self.now = timezone.now()
        self.near_place = Place.objects.create(
            name="Makolo Centre",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.664700"),
            longitude=Decimal("27.479400"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        self.farther_place = Place.objects.create(
            name="Makolo Nord",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.700000"),
            longitude=Decimal("27.520000"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )

    def activity_occurrence(self, title, *, place=None, start_delta=timedelta(days=1), visibility=ActivityVisibility.PUBLIC):
        activity = create_activity(
            created_by=self.owner,
            owner_profile=self.owner,
            title=title,
            status=ActivityStatus.PUBLISHED,
            visibility=visibility,
        )
        occurrence = create_occurrence(
            activity=activity,
            start_at=self.now + start_delta,
            end_at=self.now + start_delta + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        if place:
            OccurrencePlace.objects.create(
                occurrence=occurrence,
                place=place,
                role=OccurrencePlaceRole.PRIMARY,
            )
        return activity, occurrence

    def test_saving_generic_activity_does_not_create_business_workflow(self):
        activity, _ = self.activity_occurrence("Atelier Activity-first", place=self.near_place)
        counts = {
            "journey": Journey.objects.count(),
            "access": Access.objects.count(),
            "order": CommerceOrder.objects.count(),
            "payment": Payment.objects.count(),
            "capacity": CapacityReservation.objects.count(),
        }
        self.client.force_login(self.participant)
        response = self.client.post(
            reverse("discovery:activity-bookmark-toggle", args=[activity.pk]),
            {"next": reverse("discovery:bookmarks")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ActivityBookmark.objects.filter(user=self.participant, activity=activity).exists())
        self.assertEqual(Journey.objects.count(), counts["journey"])
        self.assertEqual(Access.objects.count(), counts["access"])
        self.assertEqual(CommerceOrder.objects.count(), counts["order"])
        self.assertEqual(Payment.objects.count(), counts["payment"])
        self.assertEqual(CapacityReservation.objects.count(), counts["capacity"])

    def test_legacy_event_toggle_writes_activity_bookmark(self):
        activity, _ = self.activity_occurrence("Événement enregistré", place=self.near_place)
        event = Event.objects.create(activity=activity, published_at=self.now)
        self.client.force_login(self.participant)
        self.client.post(reverse("discovery:bookmark-toggle", args=[event.pk]))
        self.assertTrue(ActivityBookmark.objects.filter(user=self.participant, activity=activity).exists())

    def test_discovery_is_list_first_and_map_is_nearby_only(self):
        self.activity_occurrence("Carte contextuelle", place=self.near_place)
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["nearby_active"])
        self.assertNotContains(response, 'id="discovery-map"')

        nearby = self.client.get(
            reverse("discovery:home"),
            {"lat": "-11.6647", "lon": "27.4794", "radius_km": "10"},
        )
        self.assertTrue(nearby.context["nearby_active"])
        self.assertContains(nearby, 'id="discovery-map"')
        self.assertContains(nearby, "km")

    def test_proximity_ordering_is_distance_first(self):
        near_activity, near = self.activity_occurrence(
            "Plus proche mais plus tard",
            place=self.near_place,
            start_delta=timedelta(days=2),
        )
        far_activity, far = self.activity_occurrence(
            "Plus loin mais plus tôt",
            place=self.farther_place,
            start_delta=timedelta(days=1),
        )
        result = search_occurrences(
            {
                "lat": "-11.6647",
                "lon": "27.4794",
                "radius_km": "10",
                "ordering": "proximity",
            },
            now=self.now,
        )
        self.assertTrue(result.nearby_active)
        ids = [item.activity_id for item in result.items]
        self.assertLess(ids.index(str(near_activity.pk)), ids.index(str(far_activity.pk)))
        self.assertEqual(result.items[0].occurrence_id, str(near.pk))
        self.assertNotEqual(result.items[0].occurrence_id, str(far.pk))

    def test_external_beneficiary_name_and_email_are_not_global_search_fields(self):
        activity, occurrence = self.activity_occurrence("Forum sans PII", place=self.near_place)
        guest = ExternalBeneficiary.objects.create(
            display_name="Jacques SecretGuest",
            email="secretguest@example.test",
            created_by=self.participant,
        )
        Journey.objects.create(
            initiated_by=self.participant,
            external_beneficiary=guest,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.RESERVATION,
            status=JourneyStatus.SUBMITTED,
        )
        self.assertEqual(search_occurrences({"q": "SecretGuest"}, now=self.now).total, 0)
        self.assertEqual(search_occurrences({"q": "secretguest@example.test"}, now=self.now).total, 0)

    def test_global_search_link_is_in_authenticated_navbar(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, 'aria-label="Rechercher sur Makolo"')
        self.assertContains(response, reverse("discovery:home") + "?focus=search")

    def test_my_events_route_redirects_to_personal_hub(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("discovery:my-events"))
        self.assertRedirects(response, reverse("core:participant-home"))
