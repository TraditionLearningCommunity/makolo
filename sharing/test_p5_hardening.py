import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from analytics_app.models import AnalyticsFact
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from notifications.models import Notification

from .models import ShareEnvelope
from .services import create_direct_activity_share

User = get_user_model()

@override_settings(MAKOLO_PUBLIC_BASE_URL="https://makolo.example")
class SharingP5HardeningTests(TestCase):
    def setUp(self):
        cache.clear(); self.sender = User.objects.create_user(username="p5-sender", email="p5-sender@example.test", password="pass"); self.recipient = User.objects.create_user(username="p5-recipient", email="p5-recipient@example.test", password="pass"); self.other = User.objects.create_user(username="p5-other", email="p5-other@example.test", password="pass")
        self.sender_profile = UserProfile.objects.create(user=self.sender, searchable=True); self.recipient_profile = UserProfile.objects.create(user=self.recipient, searchable=True); self.other_profile = UserProfile.objects.create(user=self.other, searchable=True)
        self.activity = Activity.objects.create(owner_profile=self.sender, created_by=self.sender, title="P5 Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        start = timezone.now() + timedelta(days=3); self.occurrence = Occurrence.objects.create(activity=self.activity, start_at=start, end_at=start + timedelta(hours=1), timezone="Africa/Lubumbashi", status=OccurrenceStatus.SCHEDULED)

    def test_duplicate_direct_share_reuses_delivery_and_notification(self):
        first = create_direct_activity_share(created_by=self.sender, recipient=self.recipient_profile, activity=self.activity); second = create_direct_activity_share(created_by=self.sender, recipient=self.recipient_profile, activity=self.activity)
        self.assertEqual(first.delivery.pk, second.delivery.pk); self.assertEqual(ShareEnvelope.objects.count(), 1); self.assertEqual(Notification.objects.filter(metadata__share_delivery_id=str(first.delivery.pk)).count(), 1)

    def test_profile_search_is_bounded_private_and_rate_limited(self):
        self.client.force_login(self.sender); response = self.client.get(reverse("sharing:profile-search"), {"q": "p5"}); self.assertEqual(response.status_code, 200); self.assertLessEqual(len(response.json()["results"]), 8); self.assertNotIn("email", json.dumps(response.json()).lower())
        for _ in range(29): self.client.get(reverse("sharing:profile-search"), {"q": "p5"})
        self.assertEqual(self.client.get(reverse("sharing:profile-search"), {"q": "p5"}).status_code, 429)

    def test_direct_share_rate_limit_returns_controlled_429(self):
        self.client.force_login(self.sender); url = reverse("sharing:create-occurrence", kwargs={"occurrence_id": self.occurrence.pk})
        profiles = [self.recipient_profile, self.other_profile]
        for index in range(12):
            if index >= len(profiles):
                user = User.objects.create_user(username=f"p5-target-{index}", email=f"p5-target-{index}@example.test", password="pass"); profiles.append(UserProfile.objects.create(user=user, searchable=True))
            self.assertEqual(self.client.post(url, {"recipient_id": profiles[index].pk}).status_code, 200)
        response = self.client.post(url, {"recipient_id": profiles[-1].pk}); self.assertEqual(response.status_code, 429); self.assertIn("Réessayez", response.json()["error"])

    def test_authenticated_delivery_open_projects_private_analytics_without_sensitive_payload(self):
        created = create_direct_activity_share(created_by=self.sender, recipient=self.recipient_profile, activity=self.activity, occurrence=self.occurrence)
        self.client.force_login(self.recipient)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk}))
        self.assertEqual(response.status_code, 200)
        events = DomainEventOutbox.objects.filter(source_id=str(created.envelope.pk)).order_by("occurred_at"); self.assertTrue(events.filter(event_type=DomainEventType.SHARE_CREATED).exists()); self.assertTrue(events.filter(event_type=DomainEventType.SHARE_DELIVERED).exists()); self.assertTrue(events.filter(event_type=DomainEventType.SHARE_OPENED).exists())
        serialized = json.dumps(list(events.values_list("payload", flat=True)), sort_keys=True)
        for secret in ("SECRET_FORM_ANSWER", "SECRET_PRIVATE_NOTE", "SECRET_PAYMENT_REF", "SECRET_ACCESS_CREDENTIAL", "SECRET_CAPTURE_TEXT"): self.assertNotIn(secret, serialized)
        self.assertTrue(AnalyticsFact.objects.filter(fact_type=DomainEventType.SHARE_OPENED, profile__isnull=True).exists())

    def test_wrong_recipient_stays_forbidden(self):
        created = create_direct_activity_share(created_by=self.sender, recipient=self.recipient_profile, activity=self.activity); self.client.force_login(self.other); self.assertEqual(self.client.get(reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})).status_code, 403)
