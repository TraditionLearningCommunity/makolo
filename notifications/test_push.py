from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.secret_box import decrypt_runtime_secret
from notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    NotificationCategory,
    NotificationKind,
    PushEndpoint,
)
from notifications.services import create_notification, dispatch_delivery


class PushEndpointApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="push-user",
            email="push@example.com",
            password="test-password",
        )
        self.other = get_user_model().objects.create_user(
            username="push-other",
            email="other@example.com",
            password="test-password",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _register(self, token="fcm-token-a", installation="installation-a"):
        return self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm",
                "platform": "android",
                "installation_id": installation,
                "token": token,
                "app_version": "1.2.3",
            },
            format="json",
        )

    def test_registers_token_encrypted_and_returns_no_secret(self):
        response = self._register()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", response.data)
        endpoint = PushEndpoint.objects.get()
        self.assertNotEqual(endpoint.encrypted_token, "fcm-token-a")
        self.assertEqual(decrypt_runtime_secret(endpoint.encrypted_token), "fcm-token-a")
        self.assertEqual(endpoint.user, self.user)
        self.assertTrue(endpoint.active)

    def test_same_installation_rotates_token_without_duplicate(self):
        self._register(token="fcm-token-a")
        self._register(token="fcm-token-b")
        self.assertEqual(PushEndpoint.objects.count(), 1)
        endpoint = PushEndpoint.objects.get()
        self.assertEqual(decrypt_runtime_secret(endpoint.encrypted_token), "fcm-token-b")

    def test_revoke_is_scoped_to_authenticated_user(self):
        self._register()
        endpoint = PushEndpoint.objects.get()
        endpoint.user = self.other
        endpoint.save(update_fields=["user", "updated_at"])

        response = self.client.delete(
            "/api/v1/notifications/push/endpoints/",
            {"provider": "fcm", "installation_id": "installation-a"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["revoked"])
        endpoint.refresh_from_db()
        self.assertTrue(endpoint.active)


class PushDeliveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="push-delivery-user",
            email="push-delivery@example.com",
        )
        PushEndpoint.objects.create(
            user=self.user,
            provider="fcm",
            platform="android",
            installation_id="installation-push",
            token_hash="0" * 64,
            encrypted_token="encrypted-for-mock",
            token_hint="push••••",
            active=True,
        )

    def test_notification_queues_push_without_storing_raw_token_in_delivery(self):
        notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Quelque chose a changé",
            message="Ouvrez Makolo.",
            queue_email=False,
        )
        delivery = notification.deliveries.get(channel=DeliveryChannel.PUSH)
        self.assertEqual(delivery.status, DeliveryStatus.QUEUED)
        self.assertTrue(delivery.destination.startswith("push:"))
        self.assertNotIn("encrypted-for-mock", delivery.destination)

    @mock.patch("notifications.services.send_push_notification", return_value="projects/makolo/messages/123")
    def test_dispatch_push_uses_endpoint_and_marks_delivery_sent(self, send):
        notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Action disponible",
            message="Ouvrez Makolo.",
            queue_email=False,
        )
        delivery = notification.deliveries.get(channel=DeliveryChannel.PUSH)

        self.assertEqual(dispatch_delivery(delivery.pk), "sent")

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.SENT)
        self.assertEqual(delivery.provider_reference, "projects/makolo/messages/123")
        send.assert_called_once()
