import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from payments.models import PaymentEvent, PaymentProvider
from payments.services import process_sandbox_webhook


class SandboxWebhookReplayTests(TestCase):
    def _body(self, *, event_id="evt-ops-1", payment_reference="PAY-ONE"):
        return json.dumps(
            {
                "id": event_id,
                "type": "payment.succeeded",
                "payment_reference": payment_reference,
                "provider_reference": "provider-1",
            },
            separators=(",", ":"),
        ).encode("utf-8")

    def _signature(self, body):
        return hmac.new(
            settings.PAYMENTS_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

    def _record_existing(self, body, event_id="evt-ops-1"):
        return PaymentEvent.objects.create(
            provider=PaymentProvider.SANDBOX,
            event_id=event_id,
            event_type="payment.succeeded",
            signature_valid=True,
            payload_hash=hashlib.sha256(body).hexdigest(),
            payload={"id": event_id, "type": "payment.succeeded"},
            processed=True,
        )

    def test_exact_signed_replay_is_idempotent(self):
        body = self._body()
        existing = self._record_existing(body)
        outcome = process_sandbox_webhook(
            raw_body=body,
            signature=self._signature(body),
        )
        self.assertTrue(outcome.duplicate)
        self.assertEqual(outcome.event.pk, existing.pk)

    def test_replay_must_still_have_valid_signature(self):
        body = self._body()
        self._record_existing(body)
        with self.assertRaises(PermissionDenied):
            process_sandbox_webhook(raw_body=body, signature="invalid-signature")

    def test_event_id_cannot_be_reused_for_different_payload(self):
        original_body = self._body(payment_reference="PAY-ONE")
        conflicting_body = self._body(payment_reference="PAY-TWO")
        self._record_existing(original_body)

        with self.assertRaises(ValidationError):
            process_sandbox_webhook(
                raw_body=conflicting_body,
                signature=self._signature(conflicting_body),
            )
