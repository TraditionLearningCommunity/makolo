from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from promotions.checkout import create_order_with_promotion
from promotions.models import DiscountType, Promotion, PromotionCode
from tickets.models import TicketType
from tickets.services import confirm_order

from .models import MarketingAttributionStatus, MarketingChannel, MarketingLink, MarketingLinkVisit


User = get_user_model()


class DiscountedGrowthAttributionTests(TestCase):
    def test_promotion_updates_source_revenue_before_confirmation(self):
        owner = User.objects.create_user(
            email="growth-promo-owner@example.com",
            username="growth-promo-owner",
            password="pass12345",
        )
        buyer = User.objects.create_user(
            email="growth-promo-buyer@example.com",
            username="growth-promo-buyer",
            password="pass12345",
        )
        organization = Organization.objects.create(name="Growth Promo Org", created_by=owner)
        OrganizationMembership.objects.create(
            organization=organization,
            user=owner,
            role=OrganizationRole.OWNER,
        )
        now = timezone.now()
        event = Event.objects.create(
            organizer=owner,
            organization=organization,
            title="Growth Promo Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=2),
            published_at=now,
        )
        ticket_type = TicketType.objects.create(
            event=event,
            name="Standard",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=20,
        )
        promotion = Promotion.objects.create(
            organization=organization,
            event=event,
            name="Growth 20",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("20.00"),
            created_by=owner,
        )
        PromotionCode.objects.create(
            promotion=promotion,
            code="GROWTH20",
            created_by=owner,
        )
        link = MarketingLink.objects.create(
            organization=organization,
            event=event,
            name="WhatsApp",
            channel=MarketingChannel.WHATSAPP,
            created_by=owner,
        )
        MarketingLinkVisit.objects.create(link=link, user=buyer)

        order = create_order_with_promotion(
            buyer=buyer,
            event=event,
            customer_name="Buyer",
            customer_email=buyer.email,
            selections=[(ticket_type, 1)],
            promotion_code="GROWTH20",
        )
        attribution = order.marketing_attribution
        self.assertEqual(order.total_amount, Decimal("20.00"))
        self.assertEqual(attribution.revenue_amount, Decimal("20.00"))
        self.assertEqual(attribution.status, MarketingAttributionStatus.PENDING)

        confirm_order(order=order, actor=owner)
        attribution.refresh_from_db()
        self.assertEqual(attribution.revenue_amount, Decimal("20.00"))
        self.assertEqual(attribution.status, MarketingAttributionStatus.CONFIRMED)
