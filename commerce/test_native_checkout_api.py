import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence
from capacity.models import CapacityPool, CapacityReservation
from commerce.models import CommerceOrder, Offer, OfferStatus, PaymentMode
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization
from payments.models import PaymentObligation


class PersonalCommerceCheckoutAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.actor = users.objects.create_user(
            username="native-checkout-user", email="checkout@example.test",
            password="test-pass-2026",
        )
        self.other = users.objects.create_user(
            username="native-checkout-other", email="other-checkout@example.test",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(name="Native Commerce", created_by=self.actor)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.actor, title="Réservation test",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
        )
        self.journey = create_journey(
            initiated_by=self.actor, beneficiary=self.actor, activity=self.activity,
            occurrence=self.occurrence, workflow=WorkflowKind.PURCHASE,
        )
        self.pool = CapacityPool.objects.create(
            activity=self.activity, occurrence=self.occurrence, total_quantity=2,
        )
        self.offer = Offer.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            capacity_pool=self.pool, name="Réservation", unit_price=Decimal("0.00"),
            currency="USD", payment_mode=PaymentMode.NONE, status=OfferStatus.ACTIVE,
        )
        self.url = reverse("commerce_api:journey-checkout", kwargs={"journey_id": self.journey.pk})

    def post(self, *, key="mobile-order-001", offer=None, quantity=1, mode="none"):
        return self.client.post(self.url, data=json.dumps({
            "idempotency_key": key,
            "offer_id": str((offer or self.offer).pk),
            "quantity": quantity,
            "payment_mode": mode,
        }), content_type="application/json")

    def test_checkout_requires_beneficiary_identity(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(CommerceOrder.objects.count(), 0)

    def test_free_checkout_is_owner_confirmed_and_idempotent(self):
        self.client.force_login(self.actor)
        listing = self.client.get(self.url)
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(listing.json()["can_order"])
        self.assertEqual(len(listing.json()["offers"]), 1)
        first = self.post()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["status"], "confirmed")
        self.assertEqual(first.json()["total"], "0.00")
        self.assertIsNone(first.json()["payment_obligation_id"])
        repeated = self.post()
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["id"], first.json()["id"])
        self.assertEqual(CommerceOrder.objects.count(), 1)
        self.assertEqual(CapacityReservation.objects.filter(journey=self.journey).count(), 1)
        self.assertEqual(PaymentObligation.objects.count(), 0)
        listing = self.client.get(self.url).json()
        self.assertFalse(listing["can_order"])
        self.assertEqual(listing["existing_order"]["id"], first.json()["id"])

    def test_second_key_does_not_create_second_order(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.post().status_code, 201)
        second = self.post(key="another-mobile-key")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(CommerceOrder.objects.count(), 1)
        self.assertEqual(CapacityReservation.objects.count(), 1)

    def test_replayed_key_cannot_change_purchase_intent(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.post().status_code, 201)
        changed = self.post(quantity=2)
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(CommerceOrder.objects.count(), 1)

    def test_foreign_offer_and_unavailable_offer_are_rejected(self):
        self.client.force_login(self.actor)
        other_activity = Activity.objects.create(
            space=self.space, created_by=self.actor, title="Other activity",
        )
        foreign = Offer.objects.create(
            activity=other_activity, name="Other", unit_price=Decimal("0.00"),
            payment_mode=PaymentMode.NONE, status=OfferStatus.ACTIVE,
        )
        self.assertEqual(self.post(offer=foreign).status_code, 404)
        self.offer.status = OfferStatus.INACTIVE
        self.offer.save()
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(CommerceOrder.objects.count(), 0)

    def test_paid_checkout_creates_obligation_not_a_successful_payment(self):
        self.client.force_login(self.actor)
        self.offer.unit_price = Decimal("25.00")
        self.offer.payment_mode = PaymentMode.UPFRONT
        self.offer.save()
        result = self.post(mode="upfront")
        self.assertEqual(result.status_code, 201)
        order = CommerceOrder.objects.get()
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.status, "pending")
        self.assertEqual(PaymentObligation.objects.filter(commerce_order=order).count(), 1)
        self.assertEqual(result.json()["payment_obligation_id"],
                         str(PaymentObligation.objects.get(commerce_order=order).pk))
        detail = self.client.get(
            reverse("personal-projections:commerce-order-detail", kwargs={"order_id": order.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["checkout"]["id"], str(order.pk))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(
            reverse("personal-projections:commerce-order-detail", kwargs={"order_id": order.pk})
        ).status_code, 404)
