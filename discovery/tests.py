from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventCategory, EventStatus, EventVenue, EventVisibility, VenueKind
from organizations.models import Organization, OrganizationFollow, OrganizationVerificationStatus
from tickets.models import TicketType

from .models import EventBookmark
from .services import build_recommendations, search_discovery_events


User = get_user_model()


class DiscoveryV1Tests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer-discovery@example.com",
            username="organizer-discovery",
            password="pass12345",
        )
        self.participant = User.objects.create_user(
            email="participant-discovery@example.com",
            username="participant-discovery",
            password="pass12345",
        )
        self.organization = Organization.objects.create(
            name="Discovery Events",
            created_by=self.organizer,
            city="Lubumbashi",
            verification_status=OrganizationVerificationStatus.VERIFIED,
        )
        self.category = EventCategory.objects.create(name="Tech Discovery")
        self.venue = EventVenue.objects.create(
            name="Hub Lubumbashi",
            kind=VenueKind.PHYSICAL,
            city="Lubumbashi",
            country="CD",
        )
        now = timezone.now()
        self.event = Event.objects.create(
            organizer=self.organizer,
            organization=self.organization,
            category=self.category,
            venue=self.venue,
            title="Makolo Tech Night",
            short_description="Rencontre tech locale",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5, hours=3),
            published_at=now,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("10.00"),
            currency="USD",
            quantity_total=100,
        )

    def _event(self, title, *, visibility=EventVisibility.PUBLIC, organization=None):
        now = timezone.now()
        return Event.objects.create(
            organizer=self.organizer,
            organization=organization or self.organization,
            category=self.category,
            venue=self.venue,
            title=title,
            status=EventStatus.PUBLISHED,
            visibility=visibility,
            start_at=now + timedelta(days=8),
            end_at=now + timedelta(days=8, hours=2),
            published_at=now,
        )

    def test_search_filters_keyword_city_and_paid(self):
        rows = list(
            search_discovery_events(
                {"q": "Tech", "city": "Lubumbashi", "price": "paid"}
            )
        )
        self.assertEqual([row.pk for row in rows], [self.event.pk])

    def test_discovery_excludes_unlisted_private_and_suspended(self):
        unlisted = self._event("Unlisted", visibility=EventVisibility.UNLISTED)
        private = self._event("Private", visibility=EventVisibility.PRIVATE)
        suspended_org = Organization.objects.create(
            name="Suspended Discovery",
            created_by=self.organizer,
            verification_status=OrganizationVerificationStatus.SUSPENDED,
        )
        suspended = self._event("Suspended", organization=suspended_org)
        ids = set(search_discovery_events({}).values_list("id", flat=True))
        self.assertIn(self.event.pk, ids)
        self.assertNotIn(unlisted.pk, ids)
        self.assertNotIn(private.pk, ids)
        self.assertNotIn(suspended.pk, ids)

    def test_bookmark_toggle_adds_then_removes(self):
        self.client.force_login(self.participant)
        url = reverse("discovery:bookmark-toggle", kwargs={"event_id": self.event.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EventBookmark.objects.filter(user=self.participant, event=self.event).exists())
        self.client.post(url)
        self.assertFalse(EventBookmark.objects.filter(user=self.participant, event=self.event).exists())

    def test_followed_organizer_boosts_explainable_recommendation(self):
        OrganizationFollow.objects.create(organization=self.organization, user=self.participant)
        rows = build_recommendations(self.participant, limit=10)
        row = next(item for item in rows if item["event"].pk == self.event.pk)
        self.assertTrue(any("suivez Discovery Events" in reason for reason in row["reasons"]))
        self.assertGreaterEqual(row["score"], 60)

    def test_bookmark_category_influences_recommendations(self):
        EventBookmark.objects.create(user=self.participant, event=self.event)
        similar = self._event("Another Tech Event")
        rows = build_recommendations(self.participant, limit=20)
        row = next(item for item in rows if item["event"].pk == similar.pk)
        self.assertTrue(any("Tech Discovery" in reason for reason in row["reasons"]))

    def test_discovery_api_does_not_expose_private_events(self):
        private = self._event("Private API Event", visibility=EventVisibility.PRIVATE)
        response = self.client.get(reverse("discovery_api:events"))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()}
        self.assertIn(str(self.event.pk), ids)
        self.assertNotIn(str(private.pk), ids)

    def test_bookmark_api_is_user_scoped(self):
        other = User.objects.create_user(
            email="other-discovery@example.com",
            username="other-discovery",
            password="pass12345",
        )
        EventBookmark.objects.create(user=other, event=self.event)
        self.client.force_login(self.participant)
        response = self.client.get(reverse("discovery_api:bookmarks"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_discovery_home_is_available_without_login(self):
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Tech Night")
