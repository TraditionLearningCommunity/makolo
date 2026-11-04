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
from notifications.push import revoke_push_endpoint_by_id


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

    def test_device_model_is_private_and_survives_a_token_rotation(self):
        registered = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm",
                "platform": "android",
                "installation_id": "visible-phone",
                "token": "one-time-token",
                "device_name": "itel S23",
            },
            format="json",
        )
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.data["device_name"], "itel S23")
        self._register(token="rotated-token", installation="visible-phone")
        endpoint = PushEndpoint.objects.get(user=self.user)
        self.assertEqual(endpoint.device_name, "itel S23")
        inventory = self.client.get("/api/v1/notifications/push/endpoints/")
        self.assertEqual(inventory.data["results"][0]["device_name"], "itel S23")
        for secret in ("visible-phone", "one-time-token", "rotated-token"):
            self.assertNotIn(secret, str(inventory.data))
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get("/api/v1/notifications/push/endpoints/").data["results"],
            [],
        )

    def test_same_installation_rotates_token_without_duplicate(self):
        self._register(token="fcm-token-a")
        self._register(token="fcm-token-b")
        self.assertEqual(PushEndpoint.objects.count(), 1)
        endpoint = PushEndpoint.objects.get()
        self.assertEqual(decrypt_runtime_secret(endpoint.encrypted_token), "fcm-token-b")

    def test_c6_device_inventory_is_owner_only_and_secret_free(self):
        self._register(token="C6-PUSH-SECRET", installation="private-device-a")
        own = PushEndpoint.objects.get(user=self.user)
        other = PushEndpoint.objects.create(
            user=self.other, provider="fcm", platform="ios",
            installation_id="private-other", token_hash="x" * 64,
            encrypted_token="other-ciphertext", token_hint="sensitive-hint",
            active=True,
        )
        listing = self.client.get("/api/v1/notifications/push/endpoints/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing["Cache-Control"], "private, no-store")
        self.assertEqual(len(listing.data["results"]), 1)
        self.assertEqual(listing.data["results"][0]["id"], str(own.pk))
        serialized = str(listing.data)
        for private in ("C6-PUSH-SECRET", "private-device-a",
                        "private-other", "sensitive-hint", "encrypted_token",
                        "token_hash", str(other.pk)):
            self.assertNotIn(private, serialized)

    def test_c6_device_revoke_by_uuid_preserves_other_user_and_is_idempotent(self):
        self._register(token="own-token", installation="my-device")
        own = PushEndpoint.objects.get(user=self.user)
        foreign = PushEndpoint.objects.create(
            user=self.other, provider="fcm", platform="ios",
            installation_id="foreign-device", token_hash="y" * 64,
            encrypted_token="foreign-encrypted", token_hint="hidden",
            active=True,
        )
        foreign_url = f"/api/v1/notifications/push/endpoints/{foreign.pk}/"
        self.assertEqual(self.client.delete(foreign_url).status_code, 404)
        foreign.refresh_from_db()
        self.assertTrue(foreign.active)
        own_url = f"/api/v1/notifications/push/endpoints/{own.pk}/"
        self.assertEqual(self.client.delete(own_url).status_code, 204)
        self.assertEqual(self.client.delete(own_url).status_code, 204)
        own.refresh_from_db()
        self.assertFalse(own.active)
        self.assertEqual(self.client.get("/api/v1/notifications/push/endpoints/").data["results"], [])

    def test_c6_revoked_device_is_not_silently_reactivated_by_token_refresh(self):
        self._register(token="before-revoke", installation="same-installation")
        endpoint = PushEndpoint.objects.get(user=self.user)
        url = f"/api/v1/notifications/push/endpoints/{endpoint.pk}/"
        self.assertEqual(self.client.delete(url).status_code, 204)
        retried = self._register(
            token="new-token-automatically-refreshed",
            installation="same-installation",
        )
        self.assertEqual(retried.status_code, 200)
        endpoint.refresh_from_db()
        self.assertFalse(endpoint.active)
        self.assertEqual(PushEndpoint.objects.count(), 1)
        explicit = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm",
                "platform": "android",
                "installation_id": "same-installation",
                "token": "token-after-user-opt-in",
                "reactivate": True,
            },
            format="json",
        )
        self.assertEqual(explicit.status_code, 200)
        endpoint.refresh_from_db()
        self.assertTrue(endpoint.active)
        self.assertEqual(
            decrypt_runtime_secret(endpoint.encrypted_token),
            "token-after-user-opt-in",
        )

    def test_c7_other_profile_cannot_silently_restore_revoked_installation(self):
        self._register(token="c7-device-token", installation="shared-c7-device")
        original = PushEndpoint.objects.get(user=self.user)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/notifications/push/endpoints/{original.pk}/"
            ).status_code, 204,
        )
        self.client.force_authenticate(self.other)
        attempted = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm",
                "platform": "android",
                "installation_id": "shared-c7-device",
                "token": "c7-device-token",
            },
            format="json",
        )
        self.assertEqual(attempted.status_code, 400)
        self.assertNotIn(str(original.pk), str(attempted.data))
        original.refresh_from_db()
        self.assertFalse(original.active)
        self.assertEqual(original.user_id, self.user.pk)

    def test_cross_profile_active_endpoint_never_moves_on_background_refresh(self):
        self._register(token="shared-device-token", installation="shared-device-id")
        endpoint = PushEndpoint.objects.get(user=self.user)
        self.client.force_authenticate(self.other)
        response = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm", "platform": "android",
                "installation_id": "shared-device-id",
                "token": "shared-device-token",
            }, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("shared-device-id", str(response.data))
        endpoint.refresh_from_db()
        self.assertTrue(endpoint.active)
        self.assertEqual(endpoint.user_id, self.user.pk)

    def test_cross_profile_explicit_transfer_requires_both_device_proofs(self):
        self._register(token="same-device-token", installation="same-device-id")
        endpoint = PushEndpoint.objects.get(user=self.user)
        self.client.force_authenticate(self.other)
        for installation, token in (
            ("same-device-id", "attacker-different-token"),
            ("attacker-different-id", "same-device-token"),
        ):
            with self.subTest(installation=installation):
                response = self.client.post(
                    "/api/v1/notifications/push/endpoints/",
                    {
                        "provider": "fcm", "platform": "android",
                        "installation_id": installation, "token": token,
                        "reactivate": True,
                    }, format="json",
                )
                self.assertEqual(response.status_code, 400)
                endpoint.refresh_from_db()
                self.assertEqual(endpoint.user_id, self.user.pk)
                self.assertTrue(endpoint.active)
                self.assertEqual(PushEndpoint.objects.count(), 1)

        wrong_platform = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm", "platform": "ios",
                "installation_id": "same-device-id",
                "token": "same-device-token", "reactivate": True,
            }, format="json",
        )
        self.assertEqual(wrong_platform.status_code, 400)
        endpoint.refresh_from_db()
        self.assertEqual(endpoint.user_id, self.user.pk)

        # An explicit opt-in from the same installation holding the current
        # FCM token transfers only the endpoint, never a Mandate or permission.
        result = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm", "platform": "android",
                "installation_id": "same-device-id",
                "token": "same-device-token", "reactivate": True,
            }, format="json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("same-device-token", str(result.data))
        endpoint.refresh_from_db()
        self.assertEqual(endpoint.user_id, self.other.pk)
        self.assertTrue(endpoint.active)
        self.assertEqual(PushEndpoint.objects.count(), 1)
        self.assertFalse(
            PushEndpoint.objects.filter(user=self.user, active=True).exists()
        )

    def test_cross_profile_revoked_endpoint_requires_explicit_opt_in(self):
        self._register(token="revoked-c8-token", installation="revoked-c8-id")
        endpoint = PushEndpoint.objects.get(user=self.user)
        self.client.delete(f"/api/v1/notifications/push/endpoints/{endpoint.pk}/")
        self.client.force_authenticate(self.other)
        attempted = self.client.post(
            "/api/v1/notifications/push/endpoints/",
            {
                "provider": "fcm", "platform": "android",
                "installation_id": "revoked-c8-id",
                "token": "revoked-c8-token",
            }, format="json",
        )
        self.assertEqual(attempted.status_code, 400)
        endpoint.refresh_from_db()
        self.assertFalse(endpoint.active)
        self.assertEqual(endpoint.user_id, self.user.pk)

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
            category=NotificationCategory.SECURITY,
            title="Quelque chose a changé",
            message="Ouvrez Makolo.",
            queue_email=False,
        )
        delivery = notification.deliveries.get(channel=DeliveryChannel.PUSH)
        self.assertEqual(delivery.status, DeliveryStatus.QUEUED)
        self.assertTrue(delivery.destination.startswith("push:"))
        self.assertNotIn("encrypted-for-mock", delivery.destination)

    def test_revoked_device_does_not_receive_queued_delivery(self):
        notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SECURITY,
            title="Information non envoyée après retrait",
            message="Push annulé.",
            queue_email=False,
        )
        delivery = notification.deliveries.get(channel=DeliveryChannel.PUSH)
        endpoint = PushEndpoint.objects.get(user=self.user)
        self.assertTrue(revoke_push_endpoint_by_id(
            user=self.user, endpoint_id=endpoint.pk,
        ))
        self.assertEqual(dispatch_delivery(delivery.pk), "skipped")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.SKIPPED)

    @mock.patch("notifications.services.send_push_notification", return_value="projects/makolo/messages/123")
    def test_dispatch_push_uses_endpoint_and_marks_delivery_sent(self, send):
        notification = create_notification(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SECURITY,
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

    def test_ordinary_information_does_not_interrupt(self):
        notification = create_notification(
            recipient=self.user, kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM, title="Information",
            message="Vous pouvez la consulter.", queue_email=True,
        )
        deliveries = list(notification.deliveries.all())
        self.assertEqual(len(deliveries), 2)
        self.assertTrue(all(d.status == DeliveryStatus.SKIPPED for d in deliveries))
        self.assertIsNone(notification.read_at)

    def test_queued_alert_honors_changed_preferences(self):
        from accounts.models import NotificationPreference
        notification = create_notification(
            recipient=self.user, kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SECURITY,
            title="Sécurité", message="Accès modifié.", queue_email=False,
        )
        delivery = notification.deliveries.get(channel=DeliveryChannel.PUSH)
        self.assertEqual(delivery.status, DeliveryStatus.QUEUED)
        NotificationPreference.objects.update_or_create(
            user=self.user, defaults={"push_notifications": False},
        )
        self.assertEqual(dispatch_delivery(delivery.pk), "skipped")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.SKIPPED)
