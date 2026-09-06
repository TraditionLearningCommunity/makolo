from types import SimpleNamespace

from django.test import SimpleTestCase

from interoperability.extensions import ExtensionDefinition, ExtensionRegistry, ExtensionSurfaceDenied
from interoperability.webhooks import (
    WebhookAuthenticationError,
    WebhookReplayError,
    WebhookSubscription,
    canonical_json_bytes,
    deliver_domain_event,
    sign_webhook,
    verify_webhook,
)


class WebhookContractTests(SimpleTestCase):
    def test_signature_round_trip_and_replay_rejected(self):
        body = canonical_json_bytes({"event": "activity.published", "id": "evt-1"})
        signature = sign_webhook(secret="test-secret", timestamp=1000, body=body)
        claimed = set()

        def claim(key):
            if key in claimed:
                return False
            claimed.add(key)
            return True

        verify_webhook(
            secret="test-secret",
            timestamp=1000,
            body=body,
            signature=signature,
            replay_key="delivery-1",
            claim_replay_key=claim,
            now=1000,
        )
        with self.assertRaises(WebhookReplayError):
            verify_webhook(
                secret="test-secret",
                timestamp=1000,
                body=body,
                signature=signature,
                replay_key="delivery-1",
                claim_replay_key=claim,
                now=1000,
            )

    def test_bad_signature_and_stale_timestamp_rejected(self):
        body = b"{}"
        with self.assertRaises(WebhookAuthenticationError):
            verify_webhook(
                secret="test-secret",
                timestamp=1000,
                body=body,
                signature="v1=bad",
                replay_key="delivery-1",
                claim_replay_key=lambda _key: True,
                now=1000,
            )
        signature = sign_webhook(secret="test-secret", timestamp=1000, body=body)
        with self.assertRaises(WebhookAuthenticationError):
            verify_webhook(
                secret="test-secret",
                timestamp=1000,
                body=body,
                signature=signature,
                replay_key="delivery-2",
                claim_replay_key=lambda _key: True,
                now=2000,
            )

    def test_outbound_delivery_uses_minimal_builder_and_injected_secret(self):
        sent = []
        subscription = WebhookSubscription(
            code="partner.activity",
            endpoint_url="https://example.test/hooks/makolo",
            event_types={"activity.published"},
            signing_key_id="partner-a",
            payload_builder=lambda event: {"event_type": event.event_type, "source_id": event.source_id},
            allow_event=lambda _event: True,
        )
        event = SimpleNamespace(event_type="activity.published", source_id="a1", payload={"private": "not-exported"})
        deliver_domain_event(
            subscription=subscription,
            event=event,
            resolve_secret=lambda key_id: "secret" if key_id == "partner-a" else "",
            transport=lambda url, body, headers: sent.append((url, body, headers)) or 202,
            timestamp=1000,
        )
        self.assertEqual(len(sent), 1)
        self.assertNotIn(b"private", sent[0][1])
        self.assertIn("X-Makolo-Webhook-Signature", sent[0][2])

    def test_outbound_endpoint_rejects_local_private_or_embedded_credentials(self):
        unsafe_urls = (
            "https://localhost/hooks",
            "https://127.0.0.1/hooks",
            "https://10.0.0.8/hooks",
            "https://user:password@example.test/hooks",
        )
        for endpoint_url in unsafe_urls:
            with self.subTest(endpoint_url=endpoint_url), self.assertRaises(ValueError):
                WebhookSubscription(
                    code="unsafe",
                    endpoint_url=endpoint_url,
                    event_types={"activity.published"},
                    signing_key_id="partner-a",
                    payload_builder=lambda _event: {},
                    allow_event=lambda _event: True,
                )


class ExtensionBoundaryTests(SimpleTestCase):
    def test_extension_can_only_compose_allowlisted_surfaces(self):
        registry = ExtensionRegistry(
            allowed_actions={"notifications.send"},
            allowed_events={"activity.published"},
            allowed_read_projections={"activity.public-summary"},
            allowed_ui_slots={"activity.detail.secondary"},
        )
        extension = registry.register(
            ExtensionDefinition(
                code="partner-helper",
                actions={"notifications.send"},
                events={"activity.published"},
                read_projections={"activity.public-summary"},
                ui_slots={"activity.detail.secondary"},
            )
        )
        self.assertEqual(extension.code, "partner-helper")

    def test_unlisted_action_or_private_surface_is_denied(self):
        registry = ExtensionRegistry(
            allowed_actions={"notifications.send"},
            allowed_events=set(),
            allowed_read_projections=set(),
            allowed_ui_slots=set(),
        )
        with self.assertRaises(ExtensionSurfaceDenied):
            registry.register(
                ExtensionDefinition(
                    code="unsafe",
                    actions={"orm.raw-write"},
                    read_projections={"profile.private"},
                )
            )
