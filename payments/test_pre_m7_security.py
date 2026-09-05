import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PaymentProvider, PaymentStatus
from .services import (
    complete_sandbox_payment,
    initiate_commerce_payment,
    initiate_payment,
    process_sandbox_webhook,
    refund_payment,
)
from .tests import make_paid_order


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True, PAYMENTS_WEBHOOK_SECRET="pre-m7-test-secret")
class PreM7PaymentSecurityTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username="pre-m7-organizer", email="organizer@pre-m7.test")
        self.buyer = User.objects.create_user(username="pre-m7-buyer", email="buyer@pre-m7.test")
        self.staff = User.objects.create_user(username="pre-m7-staff", email="staff@pre-m7.test", is_staff=True)
        self.event, self.ticket_type, self.order = make_paid_order(self.organizer, self.buyer)

    def _payment(self, key="pre-m7-payment"):
        return initiate_payment(
            order=self.order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method="card",
            idempotency_key=key,
        )

    def test_simple_staff_cannot_initiate_someone_elses_commerce_order(self):
        with self.assertRaises(PermissionDenied):
            initiate_commerce_payment(
                commerce_order=self.order.commerce_order,
                actor=self.staff,
                provider=PaymentProvider.SANDBOX,
                method="card",
            )

    def test_simple_staff_cannot_refund_payment_without_finance_mandate(self):
        payment = self._payment()
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        with self.assertRaises(PermissionDenied):
            refund_payment(payment=payment, actor=self.staff)

    def test_webhook_replay_is_idempotent_and_payload_confusion_is_rejected(self):
        payment = self._payment()
        payload = {
            "id": "pre-m7-event-1",
            "type": "payment.succeeded",
            "payment_reference": payment.reference,
            "provider_reference": "PRE-M7-PROVIDER-1",
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"pre-m7-test-secret", raw, hashlib.sha256).hexdigest()
        first = process_sandbox_webhook(raw_body=raw, signature=signature)
        second = process_sandbox_webhook(raw_body=raw, signature=signature)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(self.order.tickets.count(), 1)

        changed = {**payload, "provider_reference": "DIFFERENT"}
        changed_raw = json.dumps(changed, separators=(",", ":")).encode()
        changed_signature = hmac.new(b"pre-m7-test-secret", changed_raw, hashlib.sha256).hexdigest()
        with self.assertRaises(ValidationError):
            process_sandbox_webhook(raw_body=changed_raw, signature=changed_signature)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PreM7PaymentMassAssignmentTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username="pre-m7-api-organizer", email="api-organizer@pre-m7.test")
        self.buyer = User.objects.create_user(username="pre-m7-api-buyer", email="api-buyer@pre-m7.test")
        self.event, self.ticket_type, self.order = make_paid_order(self.organizer, self.buyer)
        self.client.force_authenticate(self.buyer)

    def test_client_amount_currency_and_status_never_override_canonical_payment(self):
        response = self.client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": str(self.order.pk),
                "provider": "sandbox",
                "method": "card",
                "amount": "1.00",
                "currency": "CDF",
                "status": "succeeded",
                "idempotency_key": "pre-m7-forged-financial-fields",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], str(self.order.total_amount))
        self.assertEqual(response.data["currency"], self.order.currency)
        self.assertEqual(response.data["status"], PaymentStatus.PENDING)
