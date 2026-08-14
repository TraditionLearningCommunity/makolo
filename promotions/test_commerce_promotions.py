from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.services import create_order
from crm.audiences import create_static_audience
from events.models import Event, EventStatus, EventVisibility
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.models import TicketType

from .canonical_models import PromotionOffer, PromotionTargeting
from .models import DiscountType, Promotion, PromotionCode


User = get_user_model()


class CommercePromotionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="commerce-promo-owner",
            email="owner@commerce-promo.test",
            password="Promo-2026!",
        )
        self.marketing = User.objects.create_user(
            username="commerce-promo-marketing",
            email="marketing@commerce-promo.test",
            password="Promo-2026!",
        )
        self.customer = User.objects.create_user(
            username="commerce-promo-customer",
            email="customer@commerce-promo.test",
            password="Promo-2026!",
        )
        self.outsider = User.objects.create_user(
            username="commerce-promo-outsider",
            email="outsider@commerce-promo.test",
            password="Promo-2026!",
        )
        self.space = Organization.objects.create(name="Commerce Promo Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Other Promo Space", created_by=self.owner)
        OrganizationMembership.objects.create(
            organization=self.space,
            user=self.marketing,
            role=OrganizationRole.MARKETING,
        )
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Commerce Promo Activity")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
        )
        self.offer = Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Tarif canonique",
            unit_price=Decimal("100.00"),
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )

    def journey(self, profile):
        return create_journey(
            initiated_by=profile,
            beneficiary=profile,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
        )

    def promotion(self, *, discount_type=DiscountType.PERCENT, discount_value="20.00", audience=None, max_redemptions=None):
        promotion = Promotion.objects.create(
            organization=self.space,
            name=f"Promo {Promotion.objects.count() + 1}",
            discount_type=discount_type,
            discount_value=Decimal(discount_value),
            currency="USD",
            max_redemptions=max_redemptions,
            max_redemptions_per_customer=10,
            created_by=self.marketing,
        )
        PromotionTargeting.objects.create(
            promotion=promotion,
            activity=self.activity,
            audience=audience,
        )
        PromotionOffer.objects.create(promotion=promotion, offer=self.offer)
        code = PromotionCode.objects.create(
            promotion=promotion,
            code=f" promo-{PromotionCode.objects.count() + 1} ",
            created_by=self.marketing,
        )
        code.refresh_from_db()
        return promotion, code

    def test_percentage_discount_targets_offer_and_snapshots_server_totals(self):
        promotion, code = self.promotion(discount_value="20.00")
        order = create_order(
            journey=self.journey(self.customer),
            buyer=self.customer,
            selections=[(self.offer, 2)],
            payee_space=self.space,
            promotion_code=code.code.lower(),
        )
        item = order.items.get()
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.discount_total, Decimal("40.00"))
        self.assertEqual(order.total, Decimal("160.00"))
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.discount_total, Decimal("40.00"))

        promotion.discount_value = Decimal("90.00")
        promotion.save(update_fields=["discount_value", "updated_at"])
        self.offer.unit_price = Decimal("500.00")
        self.offer.save(update_fields=["unit_price", "updated_at"])
        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.total, Decimal("160.00"))
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.discount_total, Decimal("40.00"))

    def test_fixed_discount_is_decimal_and_client_cannot_choose_discount(self):
        _promotion, code = self.promotion(discount_type=DiscountType.FIXED, discount_value="30.00")
        order = create_order(
            journey=self.journey(self.customer),
            buyer=self.customer,
            selections=[(self.offer, 1)],
            payee_space=self.space,
            promotion_code=code.code,
        )
        self.assertEqual(order.discount_total, Decimal("30.00"))
        self.assertEqual(order.total, Decimal("70.00"))

        with self.assertRaises(ValidationError):
            create_order(
                journey=self.journey(self.outsider),
                buyer=self.outsider,
                selections=[{"offer": self.offer, "quantity": 1, "discount_total": "99.00"}],
                payee_space=self.space,
                promotion_code=code.code,
            )

    def test_audience_restriction_cannot_be_bypassed_by_knowing_code(self):
        audience = create_static_audience(
            organization=self.space,
            name="Étudiants",
            created_by=self.marketing,
            profiles=[self.customer],
        )
        _promotion, code = self.promotion(audience=audience)

        eligible = create_order(
            journey=self.journey(self.customer),
            buyer=self.customer,
            selections=[(self.offer, 1)],
            payee_space=self.space,
            promotion_code=code.code,
        )
        self.assertEqual(eligible.total, Decimal("80.00"))

        with self.assertRaises(ValidationError):
            create_order(
                journey=self.journey(self.outsider),
                buyer=self.outsider,
                selections=[(self.offer, 1)],
                payee_space=self.space,
                promotion_code=code.code,
            )

    def test_window_inactive_and_cross_space_offer_are_rejected(self):
        promotion, code = self.promotion()
        promotion.starts_at = timezone.now() + timedelta(days=1)
        promotion.save(update_fields=["starts_at", "updated_at"])
        with self.assertRaises(ValidationError):
            create_order(
                journey=self.journey(self.customer),
                buyer=self.customer,
                selections=[(self.offer, 1)],
                payee_space=self.space,
                promotion_code=code.code,
            )

        other_activity = Activity.objects.create(space=self.other_space, created_by=self.owner, title="Other")
        other_offer = Offer.objects.create(
            activity=other_activity,
            name="Other Offer",
            unit_price=Decimal("10.00"),
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )
        target = PromotionOffer(promotion=promotion, offer=other_offer)
        with self.assertRaises(ValidationError):
            target.full_clean()

    def test_ticket_type_bridge_materializes_offer_target(self):
        event = Event.objects.create(
            organizer=self.owner,
            organization=self.space,
            title="Bridge Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=5),
            end_at=timezone.now() + timedelta(days=5, hours=2),
            published_at=timezone.now(),
            capacity=100,
        )
        ticket_type = TicketType.objects.create(
            event=event,
            name="Standard",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=100,
        )
        ticket_type.refresh_from_db()
        self.assertIsNotNone(ticket_type.offer_id)
        promotion = Promotion.objects.create(
            organization=self.space,
            event=event,
            name="Bridge Promo",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("10.00"),
            currency="USD",
            created_by=self.marketing,
        )
        promotion.eligible_ticket_types.set([ticket_type])
        self.assertTrue(
            PromotionOffer.objects.filter(
                promotion=promotion,
                offer_id=ticket_type.offer_id,
                source="ticket_type",
            ).exists()
        )
