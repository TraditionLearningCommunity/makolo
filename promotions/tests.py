from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import AudienceKind, AudienceSegment, CommunicationCampaign, CommunicationKind
from crm.selectors import campaign_metrics
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.models import TicketOrder, TicketOrderStatus, TicketType
from tickets.services import cancel_order, create_order, expire_order

from .checkout import apply_code_to_pending_order, create_order_with_promotion
from .models import DiscountType, Promotion, PromotionCode, PromotionRedemption, RedemptionStatus
from .services import public_codes_for_event, quote_promotion


User = get_user_model()


class PromotionsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="promo-owner",
            email="owner@promo.test",
            password="Strong-password-2026!",
        )
        self.marketing = User.objects.create_user(
            username="promo-marketing",
            email="marketing@promo.test",
            password="Strong-password-2026!",
        )
        self.finance = User.objects.create_user(
            username="promo-finance",
            email="finance@promo.test",
            password="Strong-password-2026!",
        )
        self.event_manager = User.objects.create_user(
            username="promo-events",
            email="events@promo.test",
            password="Strong-password-2026!",
        )
        self.customer = User.objects.create_user(
            username="promo-customer",
            email="customer@promo.test",
            password="Strong-password-2026!",
            first_name="Aline",
        )
        self.other_customer = User.objects.create_user(
            username="promo-customer-2",
            email="customer2@promo.test",
            password="Strong-password-2026!",
        )
        self.organization = Organization.objects.create(
            name="Promo Events",
            created_by=self.owner,
            public_profile=True,
        )
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.marketing, OrganizationRole.MARKETING),
            (self.finance, OrganizationRole.FINANCE),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
        ]:
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )
        self.now = timezone.now().replace(microsecond=0)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Promo Festival",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=10),
            end_at=self.now + timedelta(days=10, hours=6),
            published_at=self.now,
            capacity=300,
        )
        self.standard = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("50.00"),
            currency="USD",
            quantity_total=200,
        )
        self.vip = TicketType.objects.create(
            event=self.event,
            name="VIP",
            price=Decimal("100.00"),
            currency="USD",
            quantity_total=100,
        )

    def promotion(self, **overrides):
        data = {
            "organization": self.organization,
            "event": self.event,
            "name": f"Offre {Promotion.objects.count() + 1}",
            "discount_type": DiscountType.PERCENT,
            "discount_value": Decimal("20.00"),
            "currency": "USD",
            "max_redemptions_per_customer": 1,
            "created_by": self.marketing,
        }
        data.update(overrides)
        promotion = Promotion(**data)
        promotion.full_clean()
        promotion.save()
        return promotion

    def code(self, promotion, value=None, **overrides):
        data = {
            "promotion": promotion,
            "code": value or f"PROMO{PromotionCode.objects.count() + 1}",
            "created_by": self.marketing,
        }
        data.update(overrides)
        code = PromotionCode(**data)
        code.full_clean()
        code.save()
        return code

    def checkout(self, *, code="", buyer=None, selections=None, email=None):
        return create_order_with_promotion(
            buyer=buyer or self.customer,
            event=self.event,
            customer_name=(buyer or self.customer).full_name or "Client",
            customer_email=email or (buyer or self.customer).email,
            selections=selections or [(self.standard, 1)],
            promotion_code=code,
        )

    def test_percentage_discount_only_uses_eligible_ticket_subtotal(self):
        promotion = self.promotion(discount_value=Decimal("20.00"))
        promotion.eligible_ticket_types.set([self.vip])
        code = self.code(promotion, "VIP20")

        order = self.checkout(code=code.code, selections=[(self.standard, 1), (self.vip, 1)])
        redemption = order.promotion_redemption

        self.assertEqual(order.status, TicketOrderStatus.PENDING)
        self.assertEqual(redemption.subtotal_amount, Decimal("150.00"))
        self.assertEqual(redemption.eligible_amount, Decimal("100.00"))
        self.assertEqual(redemption.discount_amount, Decimal("20.00"))
        self.assertEqual(order.total_amount, Decimal("130.00"))
        self.assertEqual(redemption.status, RedemptionStatus.RESERVED)

    def test_fixed_discount_can_make_order_free_and_issue_tickets(self):
        promotion = self.promotion(
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50.00"),
        )
        code = self.code(promotion, "FREE50")

        order = self.checkout(code=code.code)
        order.refresh_from_db()
        redemption = PromotionRedemption.objects.get(order=order)

        self.assertEqual(order.total_amount, Decimal("0.00"))
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(order.tickets.count(), 1)
        self.assertEqual(redemption.status, RedemptionStatus.CONFIRMED)
        self.assertIsNotNone(redemption.confirmed_at)

    def test_wrong_event_code_rolls_back_order_and_stock(self):
        second_event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Autre événement",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=20),
            end_at=self.now + timedelta(days=20, hours=2),
            published_at=self.now,
        )
        promotion = self.promotion(event=second_event, name="Autre offre")
        code = self.code(promotion, "OTHER20")
        before_orders = TicketOrder.objects.count()

        with self.assertRaises(ValidationError):
            self.checkout(code=code.code)

        self.assertEqual(TicketOrder.objects.count(), before_orders)
        self.standard.refresh_from_db()
        self.assertEqual(self.standard.reserved_quantity, 0)

    def test_inactive_future_and_expired_codes_are_rejected(self):
        promotion = self.promotion()
        inactive = self.code(promotion, "OFF20", is_active=False)
        with self.assertRaises(ValidationError):
            self.checkout(code=inactive.code)

        future = self.code(
            promotion,
            "FUTURE20",
            starts_at=self.now + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            self.checkout(code=future.code)

        expired = self.code(
            promotion,
            "OLD20",
            starts_at=self.now - timedelta(days=3),
            ends_at=self.now - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            self.checkout(code=expired.code)

    def test_minimum_order_and_currency_rules_are_enforced(self):
        promotion = self.promotion(min_order_amount=Decimal("100.00"), currency="USD")
        code = self.code(promotion, "MIN100")
        with self.assertRaises(ValidationError):
            self.checkout(code=code.code, selections=[(self.standard, 1)])

        promotion.min_order_amount = Decimal("0.00")
        promotion.currency = "CDF"
        promotion.save(update_fields=["min_order_amount", "currency", "updated_at"])
        with self.assertRaises(ValidationError):
            self.checkout(code=code.code, selections=[(self.vip, 1)])

    def test_customer_limit_counts_reserved_and_confirmed_but_not_reversed(self):
        promotion = self.promotion(max_redemptions_per_customer=1)
        code = self.code(promotion, "ONCE20")
        first = self.checkout(code=code.code)

        with self.assertRaises(ValidationError):
            self.checkout(code=code.code)

        cancel_order(order=first, actor=self.customer)
        first.promotion_redemption.refresh_from_db()
        self.assertEqual(first.promotion_redemption.status, RedemptionStatus.REVERSED)

        second = self.checkout(code=code.code)
        self.assertEqual(second.promotion_redemption.status, RedemptionStatus.RESERVED)

    def test_global_and_code_quotas_are_enforced(self):
        promotion = self.promotion(max_redemptions=2, max_redemptions_per_customer=2)
        code = self.code(promotion, "LIMIT1", max_redemptions=1)
        self.checkout(code=code.code)

        with self.assertRaises(ValidationError):
            self.checkout(code=code.code, buyer=self.other_customer)

        second_code = self.code(promotion, "LIMIT2")
        self.checkout(code=second_code.code, buyer=self.other_customer)
        third_customer = User.objects.create_user(
            username="promo-customer-3",
            email="customer3@promo.test",
            password="Strong-password-2026!",
        )
        with self.assertRaises(ValidationError):
            self.checkout(code=second_code.code, buyer=third_customer)

    def test_expired_order_reverses_redemption_and_releases_quota(self):
        promotion = self.promotion(max_redemptions=1)
        code = self.code(promotion, "EXPIRE20")
        order = self.checkout(code=code.code)
        order.expires_at = self.now - timedelta(minutes=1)
        order.save(update_fields=["expires_at", "updated_at"])

        expire_order(order=order)
        redemption = PromotionRedemption.objects.get(order=order)
        self.assertEqual(redemption.status, RedemptionStatus.REVERSED)

        replacement = self.checkout(code=code.code, buyer=self.other_customer)
        self.assertEqual(replacement.promotion_redemption.status, RedemptionStatus.RESERVED)

    def test_coupon_can_be_applied_to_existing_pending_order(self):
        promotion = self.promotion()
        code = self.code(promotion, "LATE20")
        order = create_order(
            buyer=self.customer,
            event=self.event,
            customer_name=self.customer.full_name or "Client",
            customer_email=self.customer.email,
            selections=[(self.standard, 1)],
        )
        self.assertFalse(PromotionRedemption.objects.filter(order=order).exists())

        updated = apply_code_to_pending_order(order=order, actor=self.customer, promotion_code=code.code)
        self.assertEqual(updated.total_amount, Decimal("40.00"))
        self.assertEqual(updated.promotion_redemption.discount_amount, Decimal("10.00"))

        with self.assertRaises(ValidationError):
            apply_code_to_pending_order(order=updated, actor=self.customer, promotion_code=code.code)

    def test_public_listing_excludes_private_and_inactive_codes(self):
        promotion = self.promotion()
        public = self.code(promotion, "PUBLIC20", label="Visible")
        self.code(promotion, "SECRET20", is_private=True)
        self.code(promotion, "PAUSED20", is_active=False)

        values = list(public_codes_for_event(self.event).values_list("code", flat=True))
        self.assertEqual(values, [public.code])

    def test_code_is_normalized_before_unique_validation(self):
        promotion = self.promotion()
        self.code(promotion, "summer20")
        duplicate = PromotionCode(
            promotion=promotion,
            code=" Summer20 ",
            created_by=self.marketing,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_ticket_order_api_accepts_promotion_code_and_returns_snapshots(self):
        promotion = self.promotion()
        code = self.code(promotion, "API20")
        self.client.force_login(self.customer)

        response = self.client.post(
            "/api/v1/tickets/orders/",
            data={
                "event_id": str(self.event.pk),
                "customer_name": self.customer.full_name or "Client",
                "customer_email": self.customer.email,
                "promotion_code": code.code,
                "items": [{"ticket_type_id": str(self.standard.pk), "quantity": 1}],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Decimal(response.json()["subtotal_amount"]), Decimal("50.00"))
        self.assertEqual(Decimal(response.json()["discount_amount"]), Decimal("10.00"))
        self.assertEqual(Decimal(response.json()["total_amount"]), Decimal("40.00"))
        self.assertEqual(response.json()["promotion_code"], code.code)

    def test_invalid_api_code_returns_400_without_orphan_order(self):
        self.client.force_login(self.customer)
        before = TicketOrder.objects.count()
        response = self.client.post(
            "/api/v1/tickets/orders/",
            data={
                "event_id": str(self.event.pk),
                "customer_name": "Client",
                "customer_email": self.customer.email,
                "promotion_code": "NOTFOUND",
                "items": [{"ticket_type_id": str(self.standard.pk), "quantity": 1}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(TicketOrder.objects.count(), before)

    def test_marketing_manages_offers_finance_reads_money_and_event_manager_is_read_only(self):
        promotion = self.promotion()
        code = self.code(promotion, "ROLE20")
        self.checkout(code=code.code)

        self.client.force_login(self.marketing)
        response = self.client.get(reverse("promotions:detail", kwargs={"pk": promotion.pk}))
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/v1/promotions/redemptions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        self.client.force_login(self.finance)
        response = self.client.get("/api/v1/promotions/redemptions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertIn("discount_amount", response.json()[0])

        self.client.force_login(self.event_manager)
        self.assertEqual(
            self.client.get(reverse("promotions:detail", kwargs={"pk": promotion.pk})).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("promotions:create", kwargs={"slug": self.organization.slug})).status_code,
            403,
        )

    def test_finance_cannot_create_promotion_via_api_but_marketing_can(self):
        payload = {
            "organization_id": str(self.organization.pk),
            "event_id": str(self.event.pk),
            "name": "API Launch",
            "discount_type": "percent",
            "discount_value": "15.00",
            "currency": "USD",
        }
        self.client.force_login(self.finance)
        denied = self.client.post(
            "/api/v1/promotions/promotions/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.marketing)
        allowed = self.client.post(
            "/api/v1/promotions/promotions/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 201, allowed.content)

    def test_crm_campaign_metrics_track_code_conversion_separately_from_click_attribution(self):
        segment = AudienceSegment.objects.create(
            organization=self.organization,
            event=self.event,
            name="Tous Promo",
            audience_kind=AudienceKind.CONFIRMED_BUYERS,
            created_by=self.marketing,
        )
        campaign = CommunicationCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            segment=segment,
            name="Campagne Code",
            kind=CommunicationKind.MARKETING,
            subject="Votre offre",
            body="Utilisez le code.",
            created_by=self.marketing,
        )
        promotion = self.promotion(
            name="Campagne 100",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("100.00"),
        )
        code = self.code(promotion, "CRMFREE", crm_campaign=campaign)
        self.checkout(code=code.code)

        metrics = campaign_metrics(campaign)
        self.assertEqual(metrics["promotion_code_conversions"], 1)
        self.assertEqual(metrics["conversions"], 0)
        self.assertEqual(metrics["promotion_code_by_currency"][0]["revenue_amount"], Decimal("0.00"))
        self.assertEqual(metrics["promotion_code_by_currency"][0]["discount_amount"], Decimal("50.00"))

    def test_crm_campaign_from_another_organization_is_rejected(self):
        other_owner = User.objects.create_user(
            username="promo-other-owner",
            email="other-owner@promo.test",
            password="Strong-password-2026!",
        )
        other_org = Organization.objects.create(name="Other Promo Org", created_by=other_owner)
        other_segment = AudienceSegment.objects.create(
            organization=other_org,
            name="Other Audience",
            audience_kind=AudienceKind.ALL,
            created_by=other_owner,
        )
        campaign = CommunicationCampaign.objects.create(
            organization=other_org,
            segment=other_segment,
            name="Other Campaign",
            kind=CommunicationKind.MARKETING,
            subject="Other",
            body="Other",
            created_by=other_owner,
        )
        promotion = self.promotion()
        code = PromotionCode(
            promotion=promotion,
            code="WRONGCRM",
            crm_campaign=campaign,
            created_by=self.marketing,
        )
        with self.assertRaises(ValidationError):
            code.full_clean()

    def test_quote_rejects_non_eligible_selection(self):
        promotion = self.promotion()
        promotion.eligible_ticket_types.set([self.vip])
        code = self.code(promotion, "VIPONLY")
        with self.assertRaises(ValidationError):
            quote_promotion(
                code_value=code.code,
                event=self.event,
                buyer=self.customer,
                customer_email=self.customer.email,
                selections=[(self.standard, 1)],
                subtotal_amount=Decimal("50.00"),
                currency="USD",
            )
