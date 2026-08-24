import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from rest_framework import status
from rest_framework.test import APITestCase

from access.services import validate_access
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization
from tickets.models import TicketOrderStatus, TicketStatus, TicketType
from tickets.services import create_order

from .models import Payment, PaymentProvider, PaymentStatus, RefundStatus
from .services import (
    complete_manual_payment,
    complete_sandbox_payment,
    initiate_payment,
    process_sandbox_webhook,
    refund_payment,
)


User = get_user_model()


def make_payment_event(organizer):
    start_at = timezone.now() + timedelta(days=3)
    organization = Organization.objects.create(
        name=f"Makolo Payments Test Org {organizer.pk}",
        created_by=organizer,
    )
    return Event.objects.create(
        organization=organization,
        organizer=organizer,
        title="Makolo Payments Test",
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        registration_start_at=timezone.now() - timedelta(hours=1),
        registration_end_at=start_at,
        capacity=50,
        published_at=timezone.now(),
    )


def make_paid_order(organizer, buyer, *, quantity=1):
    event = make_payment_event(organizer)
    ticket_type = TicketType.objects.create(
        event=event,
        name="Pass paiement",
        price=Decimal("20.00"),
        currency="USD",
        quantity_total=10,
        max_per_order=5,
    )
    order = create_order(
        buyer=buyer,
        event=event,
        customer_name=buyer.full_name or buyer.username,
        customer_email=buyer.email,
        selections=[(ticket_type, quantity)],
    )
    return event, ticket_type, order


@override_settings(PAYMENTS_SANDBOX_ENABLED=True, PAYMENTS_WEBHOOK_SECRET="test-webhook-secret")
class PaymentServiceTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="payment-organizer",
            email="payment-organizer@example.com",
            password="Strong-payment-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="payment-buyer",
            email="payment-buyer@example.com",
            password="Strong-payment-password-2026!",
        )
        self.other = User.objects.create_user(
            username="payment-other",
            email="payment-other@example.com",
            password="Strong-payment-password-2026!",
        )
        self.event, self.ticket_type, self.order = make_paid_order(
            self.organizer,
            self.buyer,
        )

    def initiate(self, key="payment-test-key"):
        return initiate_payment(
            order=self.order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method="mobile_money",
            payer_phone="+243999000111",
            idempotency_key=key,
        )

    def test_initiate_payment_matches_order_total(self):
        payment = self.initiate()
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.amount, self.order.total_amount)
        self.assertEqual(payment.currency, self.order.currency)
        self.assertEqual(payment.order_id, self.order.pk)

    def test_initiation_is_idempotent(self):
        first = self.initiate()
        second = self.initiate()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.count(), 1)

    def test_other_user_cannot_pay_someone_elses_order(self):
        with self.assertRaises(PermissionDenied):
            initiate_payment(
                order=self.order,
                actor=self.other,
                provider=PaymentProvider.SANDBOX,
                method="card",
            )

    def test_sandbox_success_confirms_order_and_issues_ticket(self):
        payment = self.initiate()
        complete_sandbox_payment(payment=payment, actor=self.buyer)

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.ticket_type.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(self.order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(self.order.tickets.count(), 1)
        self.assertEqual(self.ticket_type.reserved_quantity, 0)
        self.assertEqual(self.ticket_type.issued_quantity, 1)

    def test_two_payments_cannot_both_confirm_same_order(self):
        first = self.initiate("first-payment")
        second = self.initiate("second-payment")
        complete_sandbox_payment(payment=first, actor=self.buyer)
        with self.assertRaises(ValidationError):
            complete_sandbox_payment(payment=second, actor=self.buyer)
        second.refresh_from_db()
        self.assertEqual(second.status, PaymentStatus.PENDING)
        self.assertEqual(self.order.tickets.count(), 1)

    def test_manual_payment_requires_event_manager(self):
        with self.assertRaises(PermissionDenied):
            initiate_payment(
                order=self.order,
                actor=self.buyer,
                provider=PaymentProvider.MANUAL,
                method="cash",
            )

        payment = initiate_payment(
            order=self.order,
            actor=self.organizer,
            provider=PaymentProvider.MANUAL,
            method="cash",
        )
        complete_manual_payment(
            payment=payment,
            actor=self.organizer,
            provider_reference="CASH-001",
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)

    def test_full_refund_cancels_order_and_valid_tickets(self):
        payment = self.initiate()
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        refund = refund_payment(
            payment=payment,
            actor=self.organizer,
            reason="Événement annulé",
            idempotency_key="refund-one",
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()
        ticket = self.order.tickets.get()
        ticket.refresh_from_db()
        self.assertEqual(refund.status, RefundStatus.SUCCEEDED)
        self.assertEqual(payment.status, PaymentStatus.REFUNDED)
        self.assertEqual(self.order.status, TicketOrderStatus.CANCELLED)
        self.assertEqual(ticket.status, TicketStatus.CANCELLED)

    def test_used_ticket_blocks_refund(self):
        payment = self.initiate()
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        ticket = self.order.tickets.get()
        validate_access(
            access=ticket.access,
            now=ticket.access.valid_from,
            source="payments-test",
        )

        with self.assertRaises(ValidationError):
            refund_payment(payment=payment, actor=self.organizer)

    def test_signed_webhook_can_complete_payment(self):
        payment = self.initiate()
        payload = {
            "id": "evt-success-001",
            "type": "payment.succeeded",
            "payment_reference": payment.reference,
            "provider_reference": "SBX-PROVIDER-001",
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(
            b"test-webhook-secret",
            raw,
            hashlib.sha256,
        ).hexdigest()

        outcome = process_sandbox_webhook(raw_body=raw, signature=signature)
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertTrue(outcome.event.processed)
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(self.order.status, TicketOrderStatus.CONFIRMED)

    def test_invalid_webhook_signature_does_not_complete_payment(self):
        payment = self.initiate()
        payload = {
            "id": "evt-invalid-001",
            "type": "payment.succeeded",
            "payment_reference": payment.reference,
        }
        raw = json.dumps(payload).encode()
        with self.assertRaises(PermissionDenied):
            process_sandbox_webhook(raw_body=raw, signature="bad-signature")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True, PAYMENTS_WEBHOOK_SECRET="test-webhook-secret")
class PaymentApiTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="payment-api-organizer",
            email="payment-api-organizer@example.com",
            password="Strong-payment-api-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="payment-api-buyer",
            email="payment-api-buyer@example.com",
            password="Strong-payment-api-password-2026!",
        )
        self.other = User.objects.create_user(
            username="payment-api-other",
            email="payment-api-other@example.com",
            password="Strong-payment-api-password-2026!",
        )
        self.event, self.ticket_type, self.order = make_paid_order(
            self.organizer,
            self.buyer,
        )

    def create_payment(self):
        self.client.force_authenticate(self.buyer)
        return self.client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": str(self.order.pk),
                "provider": "sandbox",
                "method": "mobile_money",
                "payer_phone": "+243999000222",
                "idempotency_key": "api-payment-key",
            },
            format="json",
        )

    def test_buyer_can_create_and_complete_sandbox_payment(self):
        response = self.create_payment()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment_id = response.data["id"]
        response = self.client.post(
            f"/api/v1/payments/payments/{payment_id}/sandbox-complete/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentStatus.SUCCEEDED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, TicketOrderStatus.CONFIRMED)

    def test_user_cannot_retrieve_another_users_payment(self):
        response = self.create_payment()
        payment_id = response.data["id"]
        self.client.force_authenticate(self.other)
        response = self.client.get(f"/api/v1/payments/payments/{payment_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_paid_ticket_order_no_longer_exposes_direct_confirm_action(self):
        self.client.force_authenticate(self.organizer)
        response = self.client.post(
            f"/api/v1/tickets/orders/{self.order.pk}/confirm/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PaymentWebTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="payment-web-organizer",
            email="payment-web-organizer@example.com",
            password="Strong-payment-web-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="payment-web-buyer",
            email="payment-web-buyer@example.com",
            password="Strong-payment-web-password-2026!",
        )
        self.event, self.ticket_type, self.order = make_paid_order(
            self.organizer,
            self.buyer,
        )

    def test_payment_pages_require_login(self):
        response = self.client.get(reverse("payments:list"))
        self.assertEqual(response.status_code, 302)

    def test_buyer_can_render_payment_start_page(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("payments:start", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.reference)
        self.assertNotContains(response, "Sandbox Makolo")
        self.assertContains(response, "Mode de paiement")
        self.assertContains(
            response,
            f"Payer {localize(self.order.total_amount)} {self.order.currency}",
        )
