from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility

from .models import OrganizationVerificationStatus
from .services import create_organization


User = get_user_model()


class PublicOrganizerModerationTests(TestCase):
    def test_suspended_organizer_and_events_disappear_from_public_discovery(self):
        owner = User.objects.create_user(
            username="suspended-owner",
            email="suspended@makolo.test",
            password="StrongPass2026!",
        )
        organization = create_organization(
            creator=owner,
            name="Suspended Events",
        )
        start = timezone.now() + timedelta(days=4)
        Event.objects.create(
            organizer=owner,
            organization=organization,
            title="Should Not Be Public",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            published_at=timezone.now(),
        )
        organization.verification_status = OrganizationVerificationStatus.SUSPENDED
        organization.save(update_fields=["verification_status", "updated_at"])

        profile_response = self.client.get(f"/o/{organization.slug}/")
        events_response = self.client.get("/events/")

        self.assertEqual(profile_response.status_code, 404)
        self.assertEqual(events_response.status_code, 200)
        self.assertNotContains(events_response, "Should Not Be Public")
