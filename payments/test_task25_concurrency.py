from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from activities.models import Activity, Occurrence
from commerce.models import CommerceOrder, OfferStatus, PaymentMode
from commerce.services import create_offer, create_order
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .models import Payment, PaymentMethod, PaymentProvider, PaymentStatus
from .services import complete_payment, initiate_commerce_payment


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
@skipUnless(connection.vendor == "postgresql", "Ce test exerce les verrous Payment PostgreSQL réels.")
class Task25PaymentConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.buyer = User.objects.create_user(
            username="t25-payment-race",
            email="t25-payment-race@example.test",
            password="Payments-2026!",
        )
        self.space = Organization.objects.create(
            name="T25 Payment Race",
            slug="t25-payment-race",
            created_by=self.buyer,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.buyer,
            title="T25 Payment Race Activity",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
        )
        self.offer = create_offer(
            activity=self.activity,
            occurrence=self.occurrence,
            name="T25 race offer",
            unit_price=Decimal("25.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )
        self.journey = create_journey(
            initiated_by=self.buyer,
            beneficiary=self.buyer,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
        )
        self.order = create_order(
            journey=self.journey,
            buyer=self.buyer,
            payee_space=self.space,
            selections=[(self.offer, 1)],
            idempotency_key="t25-payment-order",
            expires_at=timezone.now() + timedelta(minutes=20),
        )

    def _initiate_same_key(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            order = CommerceOrder.objects.get(pk=self.order.pk)
            buyer = User.objects.get(pk=self.buyer.pk)
            payment = initiate_commerce_payment(
                commerce_order=order,
                actor=buyer,
                provider=PaymentProvider.SANDBOX,
                method=PaymentMethod.CARD,
                idempotency_key="t25-payment-retry-same-key",
            )
            return str(payment.pk)
        finally:
            connection.close()

    def test_two_concurrent_initiations_with_same_key_return_one_payment(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._initiate_same_key, barrier) for _ in range(2)]
            payment_ids = [future.result(timeout=15) for future in futures]

        self.assertEqual(len(set(payment_ids)), 1)
        self.assertEqual(
            Payment.objects.filter(
                commerce_order=self.order,
                idempotency_key="t25-payment-retry-same-key",
            ).count(),
            1,
        )

    def _complete(self, barrier, payment_id, provider_reference):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            payment = Payment.objects.get(pk=payment_id)
            try:
                complete_payment(
                    payment=payment,
                    provider_reference=provider_reference,
                    source="t25-postgres-race",
                )
                return "success"
            except ValidationError:
                return "rejected"
        finally:
            connection.close()

    def test_two_concurrent_completions_allow_only_one_success(self):
        first = initiate_commerce_payment(
            commerce_order=self.order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            idempotency_key="t25-payment-first",
        )
        second = initiate_commerce_payment(
            commerce_order=self.order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            idempotency_key="t25-payment-second",
        )
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._complete, barrier, first.pk, "SBX-T25-RACE-1"),
                executor.submit(self._complete, barrier, second.pk, "SBX-T25-RACE-2"),
            ]
            results = [future.result(timeout=15) for future in futures]

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(
            Payment.objects.filter(
                commerce_order=self.order,
                status=PaymentStatus.SUCCEEDED,
            ).count(),
            1,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "confirmed")
