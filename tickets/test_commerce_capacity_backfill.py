from datetime import timedelta
from decimal import Decimal
from importlib import import_module

from django.contrib.auth import get_user_model
from django.apps import apps
from django.test import TestCase, override_settings
from django.utils import timezone

from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, CommerceOrderItem, Offer, PaymentMode
from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus
from organizations.models import Organization
from payments.models import Payment, PaymentMethod, PaymentProvider
from payments.services import initiate_payment

from .models import TicketOrder, TicketOrderItem, TicketOrderStatus, TicketType


backfill_tickets = import_module("tickets.migrations.0008_backfill_commerce_capacity")
backfill_payments = import_module("payments.migrations.0003_backfill_commerce_order")


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class CommerceCapacityBackfillTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="commerce-backfill",
            email="commerce-backfill@example.com",
            password="Backfill-2026!",
        )
        self.space = Organization.objects.create(name="Backfill Commerce", created_by=self.user)
        self.event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Backfill Commerce Event",
            status=EventStatus.PUBLISHED,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            registration_start_at=timezone.now() - timedelta(days=1),
            registration_end_at=timezone.now() + timedelta(days=1),
        )
        sync_event_core(self.event)
        self.event.refresh_from_db(fields=["activity"])
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Historique",
            price=Decimal("15.00"),
            currency="USD",
            quantity_total=10,
            is_active=True,
        )
        self.order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.user,
            customer_name="Historical Buyer",
            customer_email=self.user.email,
            status=TicketOrderStatus.PENDING,
            total_amount=Decimal("25.00"),
            currency="USD",
            expires_at=timezone.now() + timedelta(minutes=20),
        )
        self.item = TicketOrderItem.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            quantity=2,
            unit_price=Decimal("15.00"),
        )
        self.payment = initiate_payment(
            order=self.order,
            actor=self.user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )

    def _detach_runtime_commerce(self):
        Payment.objects.filter(pk=self.payment.pk).update(commerce_order=None)
        TicketOrderItem.objects.filter(pk=self.item.pk).update(commerce_item=None)
        TicketOrder.objects.filter(pk=self.order.pk).update(commerce_order=None)
        TicketType.objects.filter(pk=self.ticket_type.pk).update(offer=None, capacity_pool=None)
        CommerceOrderItem.objects.all().delete()
        CapacityReservation.objects.all().delete()
        CommerceOrder.objects.all().delete()
        Offer.objects.all().delete()
        CapacityPool.objects.all().delete()

    def _run_backfill(self):
        backfill_tickets.backfill_commerce_capacity(apps, None)
        backfill_payments.backfill_payment_commerce(apps, None)

    def test_backfill_preserves_historical_snapshots_and_payment_identity(self):
        payment_id = self.payment.pk
        journey_id = self.order.journey_id
        self._detach_runtime_commerce()

        # The current TicketType price must not rewrite the historical line price.
        TicketType.objects.filter(pk=self.ticket_type.pk).update(price=Decimal("99.00"))
        self._run_backfill()

        ticket_type = TicketType.objects.select_related("offer", "capacity_pool").get(pk=self.ticket_type.pk)
        order = TicketOrder.objects.select_related("commerce_order").get(pk=self.order.pk)
        item = TicketOrderItem.objects.select_related("commerce_item__capacity_reservation").get(pk=self.item.pk)
        payment = Payment.objects.get(pk=payment_id)

        self.assertEqual(ticket_type.offer.unit_price, Decimal("99.00"))
        self.assertEqual(ticket_type.capacity_pool.total_quantity, 10)
        self.assertEqual(order.commerce_order.journey_id, journey_id)
        self.assertEqual(order.commerce_order.subtotal, Decimal("30.00"))
        self.assertEqual(order.commerce_order.discount_total, Decimal("5.00"))
        self.assertEqual(order.commerce_order.total, Decimal("25.00"))
        self.assertEqual(order.commerce_order.payment_mode, PaymentMode.UPFRONT)
        self.assertEqual(item.commerce_item.unit_price, Decimal("15.00"))
        self.assertEqual(item.commerce_item.quantity, 2)
        self.assertEqual(item.commerce_item.discount_total, Decimal("5.00"))
        self.assertEqual(item.commerce_item.line_total, Decimal("25.00"))
        self.assertEqual(item.commerce_item.capacity_reservation.status, CapacityReservationStatus.HELD)
        self.assertEqual(item.commerce_item.capacity_reservation.quantity, 2)
        self.assertEqual(payment.commerce_order_id, order.commerce_order_id)
        self.assertEqual(Payment.objects.filter(pk=payment_id).count(), 1)

    def test_backfill_is_idempotent_in_intent(self):
        self._detach_runtime_commerce()
        self._run_backfill()
        ids = (
            TicketType.objects.get(pk=self.ticket_type.pk).offer_id,
            TicketType.objects.get(pk=self.ticket_type.pk).capacity_pool_id,
            TicketOrder.objects.get(pk=self.order.pk).commerce_order_id,
            TicketOrderItem.objects.get(pk=self.item.pk).commerce_item_id,
        )
        self._run_backfill()
        self.assertEqual(
            ids,
            (
                TicketType.objects.get(pk=self.ticket_type.pk).offer_id,
                TicketType.objects.get(pk=self.ticket_type.pk).capacity_pool_id,
                TicketOrder.objects.get(pk=self.order.pk).commerce_order_id,
                TicketOrderItem.objects.get(pk=self.item.pk).commerce_item_id,
            ),
        )
