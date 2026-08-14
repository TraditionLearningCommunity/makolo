from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from access.models import AccessStatus
from activities.models import Activity, Occurrence
from capacity.access_bridge import issue_access_from_capacity
from capacity.models import CapacityPool, CapacityReservationStatus
from commerce.models import CommerceOrderStatus, Offer, OfferStatus, PaymentMode
from commerce.services import create_order
from journeys.legacy_bridge import sync_legacy_journey_status
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey, request_approval, submit_journey
from organizations.models import Organization

from .models import PaymentMethod, PaymentProvider, PaymentStatus
from .services import complete_payment, initiate_commerce_payment


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class GenericCommercePaymentTests(TestCase):
    def test_after_approval_payment_commits_capacity_then_allows_access(self):
        user = get_user_model().objects.create_user(
            username="generic-commerce-payment",
            email="generic-commerce-payment@example.com",
            password="Payments-2026!",
        )
        space = Organization.objects.create(name="Generic Commerce Space", created_by=user)
        activity = Activity.objects.create(space=space, created_by=user, title="Formation sur validation")
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
        )
        journey = create_journey(
            initiated_by=user,
            beneficiary=user,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.ORDER_APPROVAL,
        )
        submit_journey(journey=journey, actor=user)
        request_approval(journey=journey, actor=user)
        sync_legacy_journey_status(
            journey=journey,
            status=JourneyStatus.APPROVED,
            actor=None,
            reason="generic-commerce-payment-test",
        )
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.APPROVED)

        pool = CapacityPool.objects.create(activity=activity, occurrence=occurrence, total_quantity=1)
        offer = Offer.objects.create(
            activity=activity,
            occurrence=occurrence,
            capacity_pool=pool,
            name="Tarif après validation",
            unit_price=Decimal("30.00"),
            currency="USD",
            payment_mode=PaymentMode.AFTER_APPROVAL,
            status=OfferStatus.ACTIVE,
        )
        order = create_order(
            journey=journey,
            buyer=user,
            payee_space=space,
            selections=[(offer, 1)],
        )
        reservation = order.items.get().capacity_reservation
        journey.refresh_from_db()
        self.assertEqual(order.status, CommerceOrderStatus.PENDING)
        self.assertEqual(reservation.status, CapacityReservationStatus.HELD)
        self.assertEqual(journey.status, JourneyStatus.PENDING_PAYMENT)

        payment = initiate_commerce_payment(
            commerce_order=order,
            actor=user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            idempotency_key="after-approval-generic-payment",
        )
        self.assertIsNone(payment.order_id)
        self.assertEqual(payment.commerce_order_id, order.pk)
        self.assertEqual(payment.amount, Decimal("30.00"))

        payment = complete_payment(
            payment=payment,
            provider_reference="SBX-AFTER-APPROVAL-001",
            source="test",
        )
        payment.refresh_from_db()
        order.refresh_from_db()
        reservation.refresh_from_db()
        journey.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(order.status, CommerceOrderStatus.CONFIRMED)
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)
        self.assertEqual(journey.status, JourneyStatus.CONFIRMED)

        access = issue_access_from_capacity(
            reservation=reservation,
            beneficiary=user,
            source_key="generic-after-approval-access",
            valid_from=None,
            valid_until=occurrence.end_at,
        )
        self.assertEqual(access.status, AccessStatus.VALID)
