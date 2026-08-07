from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role

from .models import Event, EventStatus, EventVisibility
from .services import publish_event


User = get_user_model()


class EventModelAndServiceTests(TestCase):
    def setUp(self):
        self.organizer_role = Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="Strong-event-password-2026!",
        )
        self.organizer.roles.add(self.organizer_role)
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="Strong-event-password-2026!",
        )

    def make_event(self, **overrides):
        start_at = timezone.now() + timedelta(days=7)
        data = {
            "organizer": self.organizer,
            "title": "Makolo Tech Day",
            "start_at": start_at,
            "end_at": start_at + timedelta(hours=3),
        }
        data.update(overrides)
        return Event.objects.create(**data)

    def test_event_rejects_end_before_start(self):
        start_at = timezone.now() + timedelta(days=2)
        event = Event(
            organizer=self.organizer,
            title="Invalid event",
            start_at=start_at,
            end_at=start_at - timedelta(hours=1),
        )

        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_slug_is_generated_and_stable(self):
        event = self.make_event()
        original_slug = event.slug

        event.title = "Titre modifié"
        event.save()

        self.assertTrue(original_slug)
        self.assertEqual(event.slug, original_slug)

    def test_publish_service_changes_lifecycle_state(self):
        event = self.make_event()

        publish_event(event=event, actor=self.organizer)
        event.refresh_from_db()

        self.assertEqual(event.status, EventStatus.PUBLISHED)
        self.assertIsNotNone(event.published_at)

    def test_non_owner_cannot_publish_event(self):
        event = self.make_event()

        with self.assertRaises(PermissionDenied):
            publish_event(event=event, actor=self.other_user)


class EventApiTests(APITestCase):
    def setUp(self):
        self.organizer_role = Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        self.organizer = User.objects.create_user(
            username="api-organizer",
            email="api-organizer@example.com",
            password="Strong-event-password-2026!",
        )
        self.organizer.roles.add(self.organizer_role)

        self.other_organizer = User.objects.create_user(
            username="other-organizer",
            email="other-organizer@example.com",
            password="Strong-event-password-2026!",
        )
        self.other_organizer.roles.add(self.organizer_role)

        self.regular_user = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="Strong-event-password-2026!",
        )

    def make_event(self, **overrides):
        start_at = timezone.now() + timedelta(days=10)
        data = {
            "organizer": self.organizer,
            "title": "Public event",
            "start_at": start_at,
            "end_at": start_at + timedelta(hours=2),
        }
        data.update(overrides)
        return Event.objects.create(**data)

    def test_anonymous_list_only_exposes_published_public_events(self):
        self.make_event(
            title="Visible",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            published_at=timezone.now(),
        )
        self.make_event(title="Draft")
        self.make_event(
            title="Private",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PRIVATE,
            published_at=timezone.now(),
        )

        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible"])

    def test_organizer_can_create_draft_event(self):
        self.client.force_authenticate(self.organizer)
        start_at = timezone.now() + timedelta(days=5)

        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Created through API",
                "start_at": start_at.isoformat(),
                "end_at": (start_at + timedelta(hours=2)).isoformat(),
                "visibility": EventVisibility.PUBLIC,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = Event.objects.get(title="Created through API")
        self.assertEqual(event.organizer, self.organizer)
        self.assertEqual(event.status, EventStatus.DRAFT)

    def test_regular_user_cannot_create_event(self):
        self.client.force_authenticate(self.regular_user)
        start_at = timezone.now() + timedelta(days=5)

        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Forbidden",
                "start_at": start_at.isoformat(),
                "end_at": (start_at + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_organizer_cannot_modify_foreign_draft(self):
        event = self.make_event(title="Owner draft")
        self.client.force_authenticate(self.other_organizer)

        response = self.client.patch(
            f"/api/v1/events/{event.slug}/",
            {"title": "Hijacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        event.refresh_from_db()
        self.assertEqual(event.title, "Owner draft")

    def test_owner_can_publish_event_through_action(self):
        event = self.make_event(title="Publish me")
        self.client.force_authenticate(self.organizer)

        response = self.client.post(f"/api/v1/events/{event.slug}/publish/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.PUBLISHED)


class EventWebTests(TestCase):
    def setUp(self):
        role = Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        self.organizer = User.objects.create_user(
            username="web-organizer",
            email="web-organizer@example.com",
            password="Strong-event-password-2026!",
        )
        self.organizer.roles.add(role)

    def test_event_list_requires_authentication(self):
        response = self.client.get(reverse("events:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_organizer_can_open_create_page(self):
        self.client.force_login(self.organizer)

        response = self.client.get(reverse("events:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Créer un événement")
