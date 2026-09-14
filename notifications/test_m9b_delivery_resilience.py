from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.models import (
    DeliveryStatus,
    NotificationCategory,
    NotificationKind,
)
from notifications.services import create_notification, dispatch_delivery


User = get_user_model()


class NotificationDeliveryResilienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="m9b-notification",
            email="m9b-notification@example.com",
            password="M9B-Notification-2026!",
        )

    def _delivery(self):
        notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SECURITY,
            title="M9-B delivery",
            message="Delivery resilience test",
            queue_email=True,
        )
        return notification.deliveries.get()

    def test_ambiguous_email_timeout_is_not_automatically_retried(self):
        delivery = self._delivery()

        with patch(
            "notifications.services.EmailMultiAlternatives.send",
            side_effect=TimeoutError("smtp response timeout"),
        ):
            result = dispatch_delivery(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result, "failed")
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertEqual(delivery.attempts, 1)
        self.assertTrue(delivery.last_error)

    def test_clear_pre_send_connection_failure_remains_retryable(self):
        delivery = self._delivery()

        with patch(
            "notifications.services.EmailMultiAlternatives.send",
            side_effect=ConnectionRefusedError("smtp unavailable"),
        ):
            result = dispatch_delivery(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result, "retry")
        self.assertEqual(delivery.status, DeliveryStatus.QUEUED)
        self.assertEqual(delivery.attempts, 1)
        self.assertTrue(delivery.last_error)
