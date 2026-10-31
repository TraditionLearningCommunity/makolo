from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import (
    Activity, ActivityStatus, ActivityVisibility,
    Occurrence, OccurrenceStatus,
)
from sharing.models import ShareEnvelope, ShareStatus

User = get_user_model()


@override_settings(MAKOLO_PUBLIC_BASE_URL="https://makolo.example")
class DiscoveryShareAPITests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="share-app-sender", password="test-password",
        )
        self.receiver = User.objects.create_user(
            username="share-app-receiver", password="test-password",
        )
        self.other = User.objects.create_user(
            username="share-app-other", password="test-password",
        )
        for user in (self.sender, self.receiver, self.other):
            UserProfile.objects.create(user=user, searchable=True)
        self.activity = Activity.objects.create(
            owner_profile=self.sender,
            created_by=self.sender,
            title="Atelier partagé",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        start = timezone.now() + timedelta(days=3)
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=start,
            end_at=start + timedelta(hours=1),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.share_url = reverse(
            "sharing_api:possibility",
            kwargs={"family": "activity", "item_id": self.activity.pk},
        )

    def test_guest_cannot_create_share_or_search_recipients(self):
        self.assertIn(
            self.client.post(self.share_url, {}).status_code, (401, 403),
        )
        self.assertIn(
            self.client.get(reverse("sharing_api:recipients"),
                            {"q": "receiver"}).status_code, (401, 403),
        )
        self.assertEqual(ShareEnvelope.objects.count(), 0)

    def test_external_link_is_revocable_and_resolves_public_n2(self):
        self.client.force_login(self.sender)
        response = self.client.post(self.share_url, {"intent": "view"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["state"], "link")
        link = response.json()["url"]
        self.assertTrue(link.startswith("https://makolo.example/s/"))
        token = urlsplit(link).path.split("/")[2]
        resolver = reverse("sharing_api:resolve", kwargs={"token": token})
        self.client.logout()
        target = self.client.get(resolver)
        self.assertEqual(target.status_code, 200)
        self.assertEqual(target.json()["family"], "activity")
        self.assertEqual(target.json()["id"], str(self.activity.pk))
        envelope = ShareEnvelope.objects.get()
        envelope.status = ShareStatus.REVOKED
        envelope.revoked_at = timezone.now()
        envelope.save()
        self.assertEqual(self.client.get(resolver).status_code, 404)

    def test_direct_delivery_only_resolves_for_its_recipient(self):
        self.client.force_login(self.sender)
        recipient = self.receiver.profile
        response = self.client.post(
            self.share_url,
            {"recipient_id": str(recipient.pk), "intent": "view"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["state"], "delivered")
        endpoint = reverse(
            "sharing_api:delivery",
            kwargs={"delivery_id": response.json()["delivery_id"]},
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.client.force_login(self.receiver)
        self.assertEqual(self.client.get(endpoint).status_code, 200)
        self.assertEqual(self.client.get(endpoint).json()["family"], "activity")

    def test_recipient_search_discloses_only_searchable_profiles(self):
        self.client.force_login(self.sender)
        response = self.client.get(
            reverse("sharing_api:recipients"), {"q": "receiver"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertNotIn("email", str(response.json()).lower())
