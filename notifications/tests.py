from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import NotificationPreference
from events.models import Event, EventStatus, EventVisibility
from payments.models import PaymentProvider
from payments.services import complete_sandbox_payment, initiate_payment, refund_payment
from tickets.models import TicketType
from tickets.services import create_order

from .models import (
    DeliveryStatus,
    Notification,
    NotificationCategory,
    NotificationKind,
)
from .services import create_notification, dispatch_pending, schedule_event_reminders


User = get_user_model()


def make_user(username):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Strong-notification-password-2026!",
    )


def make_event(organizer, *, hours_until=72):
    start_at = timezone.now() + timedelta(hours=hours_until)
    return Event.objects.create(
        organizer=organizer,
        title="Makolo Notifications Test",
        slug=f"notifications-{organizer.username}-{hours_until}",
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
        start_at=start_at,
        end_at=start_at + timedelta(hours=3),
        registration_start_at=timezone.now() - timedelta(hours=1),
        registration_end_at=start_at,
        capacity=100,
        published_at=timezone.now(),
    )


def make_order(organizer, buyer, *, price="0.00", hours_until=72):
    event = make_event(organizer, hours_until=hours_until)
    ticket_type = TicketType.objects.create(
        event=event,
        name="Pass notification",
        price=Decimal(price),
        currency="USD",
        quantity_total=20,
        max_per_order=5,
    )
    order = create_order(
        buyer=buyer,
        event=event,
        customer_name=buyer.username,
        customer_email=buyer.email,
        selections=[(ticket_type, 1)],
    )
    return event, ticket_type, order


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("notify-user")

    def create_one(self, **kwargs):
        defaults = {
            "recipient": self.user,
            "kind": NotificationKind.SYSTEM,
            "category": NotificationCategory.SYSTEM,
            "title": "Information Makolo",
            "message": "Une information importante.",
            "dedup_key": "test:one",
        }
        defaults.update(kwargs)
        return create_notification(**defaults)

    def test_dedup_key_is_idempotent(self):
        first = self.create_one()
        second = self.create_one()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(first.deliveries.count(), 1)

    def test_disabled_email_preference_keeps_in_app_and_skips_delivery(self):
        NotificationPreference.objects.update_or_create(
            user=self.user,
            defaults={"email_notifications": False},
        )
        notification = self.create_one()
        delivery = notification.deliveries.get()
        self.assertEqual(delivery.status, DeliveryStatus.SKIPPED)
        self.assertTrue(delivery.skipped_reason)
        self.assertEqual(Notification.objects.count(), 1)

    def test_dispatch_pending_sends_email(self):
        notification = self.create_one(action_url="/notifications/")
        result = dispatch_pending()
        delivery = notification.deliveries.get()
        delivery.refresh_from_db()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(delivery.status, DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Information Makolo", mail.outbox[0].subject)

    def test_quiet_hours_delay_email(self):
        local_now = timezone.localtime()
        start = (local_now - timedelta(minutes=5)).time().replace(second=0, microsecond=0)
        end = (local_now + timedelta(minutes=30)).time().replace(second=0, microsecond=0)
        NotificationPreference.objects.update_or_create(
            user=self.user,
            defaults={
                "email_notifications": True,
                "quiet_hours_enabled": True,
                "quiet_hours_start": start,
                "quiet_hours_end": end,
            },
        )
        notification = self.create_one(dedup_key="test:quiet")
        delivery = notification.deliveries.get()
        self.assertEqual(delivery.status, DeliveryStatus.QUEUED)
        self.assertGreater(delivery.scheduled_for, timezone.now())

    def test_external_action_url_is_not_used_as_open_redirect(self):
        notification = self.create_one(
            dedup_key="test:external",
            action_url="https://example.com/phishing",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertRedirects(response, reverse("notifications:list"))


class NotificationWebTests(TestCase):
    def setUp(self):
        self.user = make_user("web-notify")
        self.other = make_user("web-other")
        self.mine = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Ma notification",
            message="Visible seulement par moi.",
            dedup_key="web:mine",
            queue_email=False,
        )
        self.theirs = create_notification(
            recipient=self.other,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Notification privée",
            message="Ne doit pas apparaître.",
            dedup_key="web:theirs",
            queue_email=False,
        )
        self.client.force_login(self.user)

    def test_inbox_is_isolated_per_user(self):
        response = self.client.get(reverse("notifications:list"))
        self.assertContains(response, "Ma notification")
        self.assertNotContains(response, "Notification privée")

    def test_mark_read_only_updates_current_users_notification(self):
        response = self.client.post(reverse("notifications:mark-read", kwargs={"pk": self.mine.pk}))
        self.assertEqual(response.status_code, 302)
        self.mine.refresh_from_db()
        self.theirs.refresh_from_db()
        self.assertIsNotNone(self.mine.read_at)
        self.assertIsNone(self.theirs.read_at)

    def test_preferences_page_updates_email_setting(self):
        response = self.client.post(
            reverse("notifications:preferences"),
            {
                "email_notifications": "",
                "event_notifications": "on",
                "security_notifications": "on",
                "marketing_notifications": "",
                "quiet_hours_enabled": "",
                "quiet_hours_start": "",
                "quiet_hours_end": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.email_notifications)


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user = make_user("api-notify")
        self.other = make_user("api-other")
        self.notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="API notification",
            message="Test API.",
            dedup_key="api:mine",
            queue_email=False,
        )
        create_notification(
            recipient=self.other,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Autre API notification",
            message="Privée.",
            dedup_key="api:other",
            queue_email=False,
        )
        self.client.force_authenticate(self.user)

    def test_api_lists_only_current_users_notifications(self):
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        results = payload.get("results", payload)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "API notification")

    def test_api_unread_count_and_mark_read(self):
        count = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(count.status_code, 200)
        self.assertEqual(count.json()["unread_count"], 1)
        marked = self.client.post(f"/api/v1/notifications/{self.notification.pk}/read/")
        self.assertEqual(marked.status_code, 200)
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationIntegrationTests(TestCase):
    def setUp(self):
        self.organizer = make_user("notify-organizer")
        self.organizer.is_organizer = True
        self.organizer.save(update_fields=["is_organizer"])
        self.buyer = make_user("notify-buyer")

    def test_free_order_confirmation_creates_notification_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            event, ticket_type, order = make_order(self.organizer, self.buyer, price="0.00")
        notification = Notification.objects.get(
            recipient=self.buyer,
            kind=NotificationKind.TICKETS_ISSUED,
        )
        self.assertEqual(notification.metadata["order_id"], str(order.pk))

    def test_paid_payment_success_creates_payment_notification(self):
        event, ticket_type, order = make_order(self.organizer, self.buyer, price="15.00")
        payment = initiate_payment(
            order=order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method="mobile_money",
            idempotency_key="notify-payment",
        )
        with self.captureOnCommitCallbacks(execute=True):
            complete_sandbox_payment(payment=payment, actor=self.buyer)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.buyer,
                kind=NotificationKind.PAYMENT_SUCCEEDED,
            ).exists()
        )

    def test_refund_creates_refund_notification(self):
        event, ticket_type, order = make_order(self.organizer, self.buyer, price="15.00")
        payment = initiate_payment(
            order=order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method="card",
            idempotency_key="notify-refund-payment",
        )
        with self.captureOnCommitCallbacks(execute=True):
            complete_sandbox_payment(payment=payment, actor=self.buyer)
        with self.captureOnCommitCallbacks(execute=True):
            refund_payment(
                payment=payment,
                actor=self.organizer,
                idempotency_key="notify-refund",
            )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.buyer,
                kind=NotificationKind.PAYMENT_REFUNDED,
            ).exists()
        )

    def test_event_reminder_is_deduplicated(self):
        with self.captureOnCommitCallbacks(execute=True):
            event, ticket_type, order = make_order(
                self.organizer,
                self.buyer,
                price="0.00",
                hours_until=24,
            )
        Notification.objects.filter(kind=NotificationKind.TICKETS_ISSUED).delete()
        first = schedule_event_reminders(hours_before=24, window_minutes=120)
        second = schedule_event_reminders(hours_before=24, window_minutes=120)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(
            Notification.objects.filter(kind=NotificationKind.EVENT_REMINDER).count(),
            1,
        )
