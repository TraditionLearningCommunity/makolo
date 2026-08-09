import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import (
    AudienceKind,
    AudienceSegment,
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CRMContact,
    CommunicationCampaign,
    CommunicationCampaignStatus,
)
from events.models import Event, EventStatus, EventVisibility
from loyalty.models import (
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyReward,
    LoyaltyRewardRedemption,
    MembershipPlan,
    MembershipStatus,
    MembershipSubscription,
)
from organizations.models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    OrganizationRole,
)
from partners.models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    CommissionStatus,
    CommissionType,
    Partner,
    PartnerCommission,
    ReferralAttribution,
    ReferralCode,
    ReferralVisit,
)
from payments.models import Payment, PaymentStatus, Refund, RefundStatus
from promotions.models import (
    DiscountType,
    Promotion,
    PromotionCode,
    PromotionRedemption,
    RedemptionStatus,
)
from tickets.models import TicketOrder, TicketOrderStatus

from .growth import build_growth_portfolio, build_organization_growth
from .models import GrowthChannel, GrowthSpend


User = get_user_model()


class GrowthAnalyticsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="growth-owner",
            email="growth-owner@test.local",
            password="Strong-password-2026!",
        )
        self.finance = User.objects.create_user(
            username="growth-finance",
            email="growth-finance@test.local",
            password="Strong-password-2026!",
        )
        self.marketing = User.objects.create_user(
            username="growth-marketing",
            email="growth-marketing@test.local",
            password="Strong-password-2026!",
        )
        self.event_manager = User.objects.create_user(
            username="growth-events",
            email="growth-events@test.local",
            password="Strong-password-2026!",
        )
        self.scanner_manager = User.objects.create_user(
            username="growth-scanner",
            email="growth-scanner@test.local",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            username="growth-outsider",
            email="growth-outsider@test.local",
            password="Strong-password-2026!",
        )
        self.buyer_one = User.objects.create_user(
            username="growth-buyer-one",
            email="buyer-one-secret@test.local",
            password="Strong-password-2026!",
        )
        self.buyer_two = User.objects.create_user(
            username="growth-buyer-two",
            email="buyer-two-secret@test.local",
            password="Strong-password-2026!",
        )

        self.organization = Organization.objects.create(
            name="Makolo Growth Lab",
            created_by=self.owner,
        )
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.finance, OrganizationRole.FINANCE),
            (self.marketing, OrganizationRole.MARKETING),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
            (self.scanner_manager, OrganizationRole.SCANNER_MANAGER),
        ]:
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )

        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Growth Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=30),
            end_at=self.now + timedelta(days=30, hours=4),
        )

        self.order_one = self._order(
            self.buyer_one,
            Decimal("100.00"),
            "USD",
            self.now - timedelta(days=70),
        )
        self.order_two = self._order(
            self.buyer_one,
            Decimal("50.00"),
            "USD",
            self.now - timedelta(days=20),
        )
        self.order_three = self._order(
            self.buyer_two,
            Decimal("10000.00"),
            "CDF",
            self.now - timedelta(days=5),
        )

        Payment.objects.create(
            order=self.order_one,
            initiated_by=self.buyer_one,
            provider="sandbox",
            method="card",
            status=PaymentStatus.SUCCEEDED,
            amount=Decimal("100.00"),
            currency="USD",
            payer_name="Buyer One Secret",
            payer_email=self.buyer_one.email,
            succeeded_at=self.order_one.confirmed_at,
        )
        self.payment_two = Payment.objects.create(
            order=self.order_two,
            initiated_by=self.buyer_one,
            provider="sandbox",
            method="card",
            status=PaymentStatus.SUCCEEDED,
            amount=Decimal("50.00"),
            currency="USD",
            payer_name="Buyer One Secret",
            payer_email=self.buyer_one.email,
            succeeded_at=self.order_two.confirmed_at,
        )
        Payment.objects.create(
            order=self.order_three,
            initiated_by=self.buyer_two,
            provider="sandbox",
            method="mobile_money",
            status=PaymentStatus.SUCCEEDED,
            amount=Decimal("10000.00"),
            currency="CDF",
            payer_name="Buyer Two Secret",
            payer_email=self.buyer_two.email,
            succeeded_at=self.order_three.confirmed_at,
        )
        Refund.objects.create(
            payment=self.payment_two,
            requested_by=self.finance,
            status=RefundStatus.SUCCEEDED,
            amount=Decimal("10.00"),
            currency="USD",
            reason="Test LTV net",
            processed_at=self.now,
        )

        follow = OrganizationFollow.objects.create(
            organization=self.organization,
            user=self.buyer_one,
        )
        OrganizationFollow.objects.filter(pk=follow.pk).update(
            followed_at=self.now - timedelta(days=30)
        )

        self.contact, _ = CRMContact.objects.get_or_create(
            organization=self.organization,
            email=self.buyer_one.email,
            defaults={
                "user": self.buyer_one,
                "name": "Buyer One Secret",
            },
        )
        self.segment = AudienceSegment.objects.create(
            organization=self.organization,
            name="Tous Growth",
            audience_kind=AudienceKind.ALL,
            created_by=self.marketing,
        )
        self.crm_campaign = CommunicationCampaign.objects.create(
            organization=self.organization,
            segment=self.segment,
            event=self.event,
            name="CRM Growth",
            subject="Growth",
            body="Message",
            status=CommunicationCampaignStatus.SENT,
            created_by=self.marketing,
        )
        self.recipient = CampaignRecipient.objects.create(
            campaign=self.crm_campaign,
            contact=self.contact,
            user=self.buyer_one,
            email=self.buyer_one.email,
            name="Buyer One Secret",
            status=CampaignRecipientStatus.SENT,
            click_count=2,
            sent_at=self.now - timedelta(days=25),
        )
        CampaignAttribution.objects.create(
            order=self.order_two,
            campaign=self.crm_campaign,
            recipient=self.recipient,
            contact=self.contact,
            status=CampaignAttributionStatus.CONFIRMED,
            revenue_amount=Decimal("50.00"),
            currency="USD",
            confirmed_at=self.order_two.confirmed_at,
        )
        GrowthSpend.objects.create(
            organization=self.organization,
            event=self.event,
            channel=GrowthChannel.CRM,
            crm_campaign=self.crm_campaign,
            label="Création campagne CRM",
            amount=Decimal("25.00"),
            currency="USD",
            incurred_at=timezone.localdate(),
            created_by=self.finance,
        )

        self.partner = Partner.objects.create(
            organization=self.organization,
            name="Growth Partner",
            created_by=self.marketing,
        )
        self.partner_campaign = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            name="Partner Growth",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            commission_currency="CDF",
            created_by=self.marketing,
        )
        self.referral_code = ReferralCode.objects.create(
            campaign=self.partner_campaign,
            partner=self.partner,
        )
        ReferralVisit.objects.create(
            referral_code=self.referral_code,
            visitor_id=uuid.uuid4(),
            landing_path=f"/events/{self.event.slug}/",
        )
        self.partner_attribution = ReferralAttribution.objects.create(
            order=self.order_three,
            referral_code=self.referral_code,
            campaign=self.partner_campaign,
            partner=self.partner,
            status=AttributionStatus.CONFIRMED,
            confirmed_at=self.order_three.confirmed_at,
        )
        PartnerCommission.objects.create(
            attribution=self.partner_attribution,
            partner=self.partner,
            campaign=self.partner_campaign,
            order=self.order_three,
            amount=Decimal("1000.00"),
            currency="CDF",
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            status=CommissionStatus.EARNED,
        )

        self.promotion = Promotion.objects.create(
            organization=self.organization,
            event=self.event,
            name="Growth Promo",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("10.00"),
            currency="USD",
            created_by=self.marketing,
        )
        self.promo_code = PromotionCode.objects.create(
            promotion=self.promotion,
            code="GROWTH10",
            created_by=self.marketing,
        )
        PromotionRedemption.objects.create(
            promotion=self.promotion,
            code=self.promo_code,
            order=self.order_two,
            buyer=self.buyer_one,
            customer_email=self.buyer_one.email,
            status=RedemptionStatus.CONFIRMED,
            subtotal_amount=Decimal("60.00"),
            eligible_amount=Decimal("60.00"),
            discount_amount=Decimal("10.00"),
            final_amount=Decimal("50.00"),
            currency="USD",
            confirmed_at=self.order_two.confirmed_at,
        )

        self.loyalty_program = LoyaltyProgram.objects.create(
            organization=self.organization,
            name="Growth Loyalty",
            created_by=self.marketing,
        )
        LoyaltyAccount.objects.create(
            program=self.loyalty_program,
            user=self.buyer_one,
            points_balance=100,
            lifetime_earned=100,
        )
        self.membership_plan = MembershipPlan.objects.create(
            program=self.loyalty_program,
            name="Club",
            code="CLUB",
            price=0,
            currency="USD",
            duration_days=365,
            created_by=self.marketing,
        )
        MembershipSubscription.objects.create(
            program=self.loyalty_program,
            plan=self.membership_plan,
            user=self.buyer_one,
            status=MembershipStatus.ACTIVE,
            price_amount=0,
            currency="USD",
            starts_at=self.now - timedelta(days=10),
            ends_at=self.now + timedelta(days=355),
            activated_at=self.now - timedelta(days=10),
            activated_by=self.buyer_one,
            activation_source="free",
        )
        reward = LoyaltyReward.objects.create(
            program=self.loyalty_program,
            name="Badge Growth",
            points_cost=20,
            created_by=self.marketing,
        )
        account = LoyaltyAccount.objects.get(program=self.loyalty_program, user=self.buyer_one)
        LoyaltyRewardRedemption.objects.create(
            account=account,
            reward=reward,
            user=self.buyer_one,
            status="redeemed",
            points_cost=20,
        )

    def _order(self, buyer, amount, currency, confirmed_at):
        return TicketOrder.objects.create(
            event=self.event,
            buyer=buyer,
            customer_name=f"Secret {buyer.username}",
            customer_email=buyer.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=amount,
            currency=currency,
            confirmed_at=confirmed_at,
        )

    def test_repeat_buyers_follow_conversion_and_cohorts(self):
        growth = build_organization_growth(self.organization, self.owner)

        self.assertEqual(growth["customer_metrics"]["customers"], 2)
        self.assertEqual(growth["customer_metrics"]["repeat_customers"], 1)
        self.assertEqual(growth["customer_metrics"]["repeat_buyer_percent"], 50.0)
        self.assertEqual(growth["followers"]["followers"], 1)
        self.assertEqual(growth["followers"]["followers_converted"], 1)
        self.assertEqual(growth["followers"]["follower_to_buyer_percent"], 100.0)
        buyer_one_cohort = next(
            row
            for row in growth["cohorts"]
            if row["size"] == 1 and row["months"][0]["active_customers"] == 1
        )
        self.assertTrue(buyer_one_cohort["months"])

    def test_finance_ltv_is_net_and_never_crosses_currencies(self):
        growth = build_organization_growth(self.organization, self.finance)
        rows = {row["currency"]: row for row in growth["ltv_by_currency"]}

        self.assertTrue(growth["financial_visible"])
        self.assertEqual(rows["USD"]["gross"], Decimal("150.00"))
        self.assertEqual(rows["USD"]["refunds"], Decimal("10.00"))
        self.assertEqual(rows["USD"]["net"], Decimal("140.00"))
        self.assertEqual(rows["USD"]["average_net_ltv"], Decimal("140.00"))
        self.assertEqual(rows["CDF"]["net"], Decimal("10000.00"))

    def test_crm_partner_and_promotion_contribution_are_currency_scoped(self):
        growth = build_organization_growth(self.organization, self.finance)

        crm_usd = growth["channels"]["crm"]["money"][0]
        self.assertEqual(crm_usd["currency"], "USD")
        self.assertEqual(crm_usd["attributed_revenue"], Decimal("50.00"))
        self.assertEqual(crm_usd["configured_spend"], Decimal("25.00"))
        self.assertEqual(crm_usd["contribution_roi_percent"], 100.0)

        partner_cdf = growth["channels"]["partners"]["money"][0]
        self.assertEqual(partner_cdf["currency"], "CDF")
        self.assertEqual(partner_cdf["attributed_revenue"], Decimal("10000.00"))
        self.assertEqual(partner_cdf["intrinsic_cost"], Decimal("1000.00"))
        self.assertEqual(partner_cdf["contribution_roi_percent"], 900.0)

        promo_usd = growth["channels"]["promotions"]["money"][0]
        self.assertEqual(promo_usd["attributed_revenue"], Decimal("50.00"))
        self.assertEqual(promo_usd["intrinsic_cost"], Decimal("10.00"))
        self.assertEqual(promo_usd["contribution_roi_percent"], 400.0)

    def test_loyalty_exposes_retention_correlation_without_claiming_causality(self):
        growth = build_organization_growth(self.organization, self.owner)
        loyalty = growth["channels"]["loyalty"]

        self.assertEqual(loyalty["accounts"], 1)
        self.assertEqual(loyalty["active_memberships"], 1)
        self.assertEqual(loyalty["reward_redemptions"], 1)
        self.assertEqual(loyalty["loyalty_repeat_buyer_percent"], 100.0)
        self.assertEqual(loyalty["non_loyalty_repeat_buyer_percent"], 0.0)
        self.assertEqual(loyalty["repeat_rate_lift_points"], 100.0)
        self.assertIn("corrélation", growth["insights"][-1]["body"].lower())

    def test_marketing_sees_growth_but_no_money_or_pii(self):
        self.client.force_login(self.marketing)
        response = self.client.get(
            reverse("analytics_api:growth-organization", args=[self.organization.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["financial_visible"])
        self.assertEqual(response.data["ltv_by_currency"], [])
        self.assertEqual(response.data["channels"]["crm"]["money"], [])
        payload = response.content.decode()
        self.assertNotIn(self.buyer_one.email, payload)
        self.assertNotIn("Buyer One Secret", payload)
        self.assertNotIn(self.payment_two.reference, payload)

    def test_event_manager_gets_operational_growth_but_scanner_manager_does_not(self):
        self.client.force_login(self.event_manager)
        allowed = self.client.get(
            reverse("analytics:growth-organization", args=[self.organization.slug])
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Métriques financières masquées")

        self.client.force_login(self.scanner_manager)
        denied = self.client.get(
            reverse("analytics:growth-organization", args=[self.organization.slug])
        )
        self.assertEqual(denied.status_code, 404)

    def test_outsider_cannot_open_growth_organization(self):
        self.client.force_login(self.outsider)
        web = self.client.get(
            reverse("analytics:growth-organization", args=[self.organization.slug])
        )
        api = self.client.get(
            reverse("analytics_api:growth-organization", args=[self.organization.slug])
        )
        self.assertEqual(web.status_code, 404)
        self.assertEqual(api.status_code, 404)

    def test_finance_can_create_spend_but_marketing_cannot(self):
        self.client.force_login(self.finance)
        response = self.client.post(
            reverse("analytics:growth-spend-new", args=[self.organization.slug]),
            {
                "channel": GrowthChannel.OTHER,
                "label": "Studio créatif",
                "amount": "12.50",
                "currency": "usd",
                "incurred_at": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GrowthSpend.objects.filter(label="Studio créatif", currency="USD").exists()
        )

        self.client.force_login(self.marketing)
        denied = self.client.get(
            reverse("analytics:growth-spend-new", args=[self.organization.slug])
        )
        self.assertEqual(denied.status_code, 403)

    def test_growth_spend_rejects_cross_organization_source(self):
        other = Organization.objects.create(name="Other Growth", created_by=self.outsider)
        other_event = Event.objects.create(
            organizer=self.outsider,
            organization=other,
            title="Other Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=10),
            end_at=self.now + timedelta(days=10, hours=2),
        )
        spend = GrowthSpend(
            organization=self.organization,
            event=other_event,
            channel=GrowthChannel.OTHER,
            label="Cross org",
            amount=Decimal("10.00"),
            currency="USD",
            created_by=self.finance,
        )
        with self.assertRaises(ValidationError):
            spend.full_clean()

    def test_growth_spend_api_is_finance_scoped(self):
        self.client.force_login(self.finance)
        response = self.client.get(reverse("analytics_api:growth-spends"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        self.client.force_login(self.marketing)
        response = self.client.get(reverse("analytics_api:growth-spends"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_growth_portfolio_is_organization_scoped(self):
        other = Organization.objects.create(name="Hidden Growth", created_by=self.outsider)
        OrganizationMembership.objects.create(
            organization=other,
            user=self.outsider,
            role=OrganizationRole.OWNER,
        )
        portfolio = build_growth_portfolio(self.marketing)
        names = {row["organization"].name for row in portfolio["cards"]}
        self.assertIn(self.organization.name, names)
        self.assertNotIn(other.name, names)
