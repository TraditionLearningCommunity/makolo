import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from capacity.models import CapacityPool, CapacityReservation
from commerce.models import CommerceOrder, Offer, OfferStatus, PaymentMode
from journeys.models import Journey, WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization
from payments.models import Payment, PaymentObligation


class ActivityCheckoutAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(
            username="direct-commerce-buyer", email="buyer@example.test",
            password="test-pass-2026",
        )
        self.other = users.objects.create_user(
            username="direct-commerce-other", email="other@example.test",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(name="Direct Commerce", created_by=self.user)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.user, title="Place à réserver",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity, status=OccurrenceStatus.SCHEDULED,
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=3, hours=2),
        )
        self.pool = CapacityPool.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            total_quantity=3,
        )
        self.offer = Offer.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            capacity_pool=self.pool, name="Réservation",
            unit_price=Decimal("0.00"), currency="USD",
            payment_mode=PaymentMode.NONE, status=OfferStatus.ACTIVE,
        )
        self.url = reverse("commerce_api:activity-checkout", kwargs={
            "activity_id": self.activity.pk,
        })

    def send(self, *, key="direct-order-01", quantity=1, mode="none", occurrence=None):
        return self.client.post(
            self.url,
            data=json.dumps({
                "idempotency_key": key,
                "offer_id": str(self.offer.pk),
                "occurrence_id": str(occurrence or self.occurrence.pk),
                "quantity": quantity,
                "payment_mode": mode,
            }),
            content_type="application/json",
        )

    def test_guest_can_browse_offers_but_cannot_mutate(self):
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["can_order"])
        self.assertEqual(result.json()["offers"][0]["occurrence_id"], str(self.occurrence.pk))
        self.assertIn(self.send().status_code, (401, 403))
        self.assertEqual(Journey.objects.count(), 0)

    def test_create_is_atomic_and_does_not_double_hold_capacity(self):
        self.client.force_login(self.user)
        first = self.send()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["status"], "confirmed")
        self.assertIsNone(first.json()["payment_obligation_id"])
        second = self.send()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(CommerceOrder.objects.count(), 1)
        self.assertEqual(Journey.objects.count(), 1)
        self.assertEqual(CapacityReservation.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)
        conflict = self.send(key="direct-order-02")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Journey.objects.count(), 1)
        self.assertEqual(CommerceOrder.objects.count(), 1)

    def test_direct_checkout_reuses_existing_purchase_draft(self):
        self.client.force_login(self.user)
        existing = create_journey(
            initiated_by=self.user, beneficiary=self.user,
            activity=self.activity, occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
        )
        result = self.send()
        self.assertEqual(result.status_code, 201)
        order = CommerceOrder.objects.get()
        self.assertEqual(order.journey_id, existing.pk)
        self.assertEqual(Journey.objects.count(), 1)

    def test_replay_must_preserve_buyer_occurrence_and_quantity(self):
        self.client.force_login(self.user)
        self.assertEqual(self.send().status_code, 201)
        self.assertEqual(self.send(quantity=2).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.send().status_code, 400)
        self.assertEqual(Journey.objects.count(), 1)

    def test_offer_context_and_private_owner_are_enforced(self):
        self.client.force_login(self.user)
        other_occurrence = Occurrence.objects.create(
            activity=self.activity, status=OccurrenceStatus.SCHEDULED,
            start_at=timezone.now() + timedelta(days=5),
            end_at=timezone.now() + timedelta(days=5, hours=1),
        )
        self.assertEqual(self.send(occurrence=other_occurrence.pk).status_code, 400)
        self.assertEqual(CommerceOrder.objects.count(), 0)
        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.send().status_code, 404)

    def test_online_paid_order_creates_obligation_not_payment(self):
        self.client.force_login(self.user)
        self.offer.unit_price = Decimal("19.00")
        self.offer.payment_mode = PaymentMode.UPFRONT
        self.offer.save()
        result = self.send(mode="upfront")
        self.assertEqual(result.status_code, 201)
        order = CommerceOrder.objects.get()
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.total, Decimal("19.00"))
        obligation = PaymentObligation.objects.get(commerce_order=order)
        self.assertEqual(result.json()["payment_obligation_id"], str(obligation.pk))
        self.assertEqual(Payment.objects.count(), 0)
