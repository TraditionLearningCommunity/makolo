import threading
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.services import create_order
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .canonical_models import CommercePromotionRedemption, PromotionOffer, PromotionTargeting
from .models import DiscountType, Promotion, PromotionCode


User = get_user_model()


class CommercePromotionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Ce test vérifie les verrous de lignes PostgreSQL réels.")
        self.owner = User.objects.create_user(username="promo-lock-owner", email="lock-owner@promo.test")
        self.first = User.objects.create_user(username="promo-lock-first", email="lock-first@promo.test")
        self.second = User.objects.create_user(username="promo-lock-second", email="lock-second@promo.test")
        self.space = Organization.objects.create(name="Promo Lock Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Quota Activity")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
        )
        self.offer = Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Quota Offer",
            unit_price=Decimal("50.00"),
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )
        self.promotion = Promotion.objects.create(
            organization=self.space,
            name="Usage unique",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("10.00"),
            currency="USD",
            max_redemptions=1,
            max_redemptions_per_customer=10,
            created_by=self.owner,
        )
        PromotionTargeting.objects.create(promotion=self.promotion, activity=self.activity)
        PromotionOffer.objects.create(promotion=self.promotion, offer=self.offer)
        self.code = PromotionCode.objects.create(
            promotion=self.promotion,
            code="UNIQUE1",
            created_by=self.owner,
        )
        self.journeys = [
            create_journey(
                initiated_by=profile,
                beneficiary=profile,
                activity=self.activity,
                occurrence=self.occurrence,
                workflow=WorkflowKind.PURCHASE,
            )
            for profile in (self.first, self.second)
        ]

    def test_quota_one_allows_only_one_concurrent_commerce_order(self):
        barrier = threading.Barrier(2)
        results = []
        results_lock = threading.Lock()

        def attempt(journey_id, profile_id):
            close_old_connections()
            try:
                journey = type(self.journeys[0]).objects.get(pk=journey_id)
                profile = User.objects.get(pk=profile_id)
                offer = Offer.objects.get(pk=self.offer.pk)
                space = Organization.objects.get(pk=self.space.pk)
                barrier.wait()
                order = create_order(
                    journey=journey,
                    buyer=profile,
                    selections=[(offer, 1)],
                    payee_space=space,
                    promotion_code="UNIQUE1",
                )
                outcome = ("success", str(order.pk))
            except ValidationError as exc:
                outcome = ("quota", " ".join(exc.messages))
            finally:
                connection.close()
            with results_lock:
                results.append(outcome)

        threads = [
            threading.Thread(target=attempt, args=(journey.pk, profile.pk))
            for journey, profile in zip(self.journeys, (self.first, self.second))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual([kind for kind, _value in results].count("success"), 1)
        self.assertEqual([kind for kind, _value in results].count("quota"), 1)
        self.assertEqual(CommercePromotionRedemption.objects.count(), 1)
