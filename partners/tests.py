from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from payments.models import PaymentMethod, PaymentProvider, PaymentStatus
from payments.services import complete_sandbox_payment, initiate_payment, refund_payment
from tickets.models import TicketOrderStatus, TicketType
from tickets.services import create_order

from .models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    CommissionStatus,
    CommissionType,
    Partner,
    PartnerCommission,
    PartnerPayout,
    PartnerStatus,
    PayoutStatus,
    ReferralAttribution,
    ReferralCode,
    ReferralVisit,
)
from .services import (
    attribute_order,
    build_partner_metrics,
    create_campaign,
    create_partner,
    create_payout,
    create_referral_code,
    mark_payout_paid,
)


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PartnerAffiliationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="partner-owner",
            email="owner-partners@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.marketing = User.objects.create_user(
            username="partner-marketing",
            email="marketing-partners@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.finance = User.objects.create_user(
            username="partner-finance",
            email="finance-partners@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.ambassador_user = User.objects.create_user(
            username="ambassador",
            email="ambassador@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.other_ambassador = User.objects.create_user(
            username="other-ambassador",
            email="other-ambassador@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.buyer = User.objects.create_user(
            username="affiliate-buyer",
            email="buyer-affiliate@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.organization = Organization.objects.create(
            name="Makolo Growth Lab",
            created_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationRole.OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.marketing,
            role=OrganizationRole.MARKETING,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.finance,
            role=OrganizationRole.FINANCE,
        )
        start = timezone.now() + timedelta(days=14)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Growth Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            published_at=timezone.now(),
            capacity=100,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("100.00"),
            currency="USD",
            quantity_total=100,
        )
        self.partner = Partner.objects.create(
            organization=self.organization,
            user=self.ambassador_user,
            name="Alice Ambassador",
            email=self.ambassador_user.email,
            status=PartnerStatus.ACTIVE,
            created_by=self.owner,
        )
        self.other_partner = Partner.objects.create(
            organization=self.organization,
            user=self.other_ambassador,
            name="Other Ambassador",
            email=self.other_ambassador.email,
            status=PartnerStatus.ACTIVE,
            created_by=self.owner,
        )
        self.campaign = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            name="Launch ambassadors",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            commission_currency="USD",
            attribution_window_days=30,
            created_by=self.owner,
        )
        self.code = ReferralCode.objects.create(
            campaign=self.campaign,
            partner=self.partner,
            code="ALICE10",
        )

    def _order(self, *, amount_paid=True):
        return create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer Affiliate",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )

    def test_marketing_can_manage_partners_but_finance_cannot(self):
        partner = create_partner(
            organization=self.organization,
            actor=self.marketing,
            name="Creator Two",
            email="creator-two@example.com",
        )
        self.assertEqual(partner.organization, self.organization)
        with self.assertRaises(PermissionDenied):
            create_partner(
                organization=self.organization,
                actor=self.finance,
                name="Finance should not create",
            )

    def test_campaign_validates_organization_event_boundary(self):
        other_org = Organization.objects.create(name="Other Org", created_by=self.owner)
        campaign = AffiliateCampaign(
            organization=other_org,
            event=self.event,
            name="Wrong scope",
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("5.00"),
        )
        with self.assertRaises(ValidationError):
            campaign.full_clean()

    def test_referral_landing_records_anonymous_visit_without_ip(self):
        response = self.client.get(
            reverse("partners:referral-landing", kwargs={"code": self.code.code}),
            HTTP_REFERER="https://social.example/post?secret=123",
            REMOTE_ADDR="203.0.113.10",
        )
        self.assertEqual(response.status_code, 302)
        visit = ReferralVisit.objects.get(referral_code=self.code)
        self.assertEqual(visit.referrer_domain, "social.example")
        self.assertNotIn("203.0.113.10", str(visit.__dict__))
        self.assertEqual(self.client.session["makolo_referral_code"], self.code.code)

    def test_web_checkout_attributes_order_from_referral_session(self):
        self.client.force_login(self.buyer)
        self.client.get(reverse("partners:referral-landing", kwargs={"code": self.code.code}))
        response = self.client.post(
            reverse("tickets:order-create", kwargs={"event_slug": self.event.slug}),
            {
                f"quantity_{self.ticket_type.pk}": "1",
                "customer_name": "Buyer Affiliate",
                "customer_email": self.buyer.email,
            },
        )
        self.assertEqual(response.status_code, 302)
        attribution = ReferralAttribution.objects.select_related("order").get(partner=self.partner)
        self.assertEqual(attribution.order.status, TicketOrderStatus.PENDING)
        self.assertEqual(attribution.status, AttributionStatus.PENDING)
        self.assertFalse(PartnerCommission.objects.filter(attribution=attribution).exists())

    def test_paid_order_earns_percentage_commission_only_after_payment_success(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        self.assertFalse(PartnerCommission.objects.exists())

        payment = initiate_payment(
            order=order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )
        complete_sandbox_payment(payment=payment, actor=self.buyer)

        attribution = ReferralAttribution.objects.get(order=order)
        commission = PartnerCommission.objects.get(attribution=attribution)
        self.assertEqual(attribution.status, AttributionStatus.CONFIRMED)
        self.assertEqual(commission.amount, Decimal("10.00"))
        self.assertEqual(commission.currency, "USD")
        self.assertEqual(commission.status, CommissionStatus.EARNED)

    def test_refund_reverses_unpaid_commission(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(
            order=order,
            actor=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )
        payment = complete_sandbox_payment(payment=payment, actor=self.buyer)
        refund_payment(payment=payment, actor=self.finance, reason="Client request")

        attribution = ReferralAttribution.objects.get(order=order)
        commission = PartnerCommission.objects.get(attribution=attribution)
        self.assertEqual(attribution.status, AttributionStatus.REVERSED)
        self.assertEqual(commission.status, CommissionStatus.REVERSED)

    def test_finance_can_prepare_and_mark_partner_payout_paid(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)

        payout = create_payout(partner=self.partner, actor=self.finance, currency="USD")
        self.assertEqual(payout.amount, Decimal("10.00"))
        self.assertEqual(payout.status, PayoutStatus.DRAFT)
        payout = mark_payout_paid(payout=payout, actor=self.finance, reference="BANK-001")
        self.assertEqual(payout.status, PayoutStatus.PAID)
        commission = PartnerCommission.objects.get(partner=self.partner)
        self.assertEqual(commission.status, CommissionStatus.PAID)
        self.assertEqual(commission.payout, payout)

    def test_paid_commission_blocks_silent_refund_reversal(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        payment = complete_sandbox_payment(payment=payment, actor=self.buyer)
        payout = create_payout(partner=self.partner, actor=self.finance, currency="USD")
        mark_payout_paid(payout=payout, actor=self.finance, reference="BANK-PAID")

        with self.assertRaises(ValidationError):
            refund_payment(payment=payment, actor=self.finance, reason="Late refund")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)

    def test_partner_metrics_are_aggregate_and_do_not_include_buyer_pii(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        metrics = build_partner_metrics(self.partner, finance_visible=True)
        payload = str(metrics)
        self.assertEqual(metrics["confirmed_orders"], 1)
        self.assertNotIn(self.buyer.email, payload)
        self.assertNotIn("Buyer Affiliate", payload)

    def test_partner_user_cannot_view_another_partner_profile(self):
        self.client.force_login(self.ambassador_user)
        response = self.client.get(reverse("partners:partner-detail", kwargs={"pk": self.other_partner.pk}))
        self.assertEqual(response.status_code, 404)

    def test_marketing_metrics_redact_commission_money(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)

        self.client.force_login(self.marketing)
        response = self.client.get(reverse("partners_api:partner-metrics", kwargs={"pk": self.partner.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["commissions"], [])

    def test_finance_metrics_include_commissions(self):
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)

        self.client.force_login(self.finance)
        response = self.client.get(reverse("partners_api:partner-metrics", kwargs={"pk": self.partner.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["commissions"][0]["currency"], "USD")

    def test_api_ticket_order_accepts_referral_code(self):
        self.client.force_login(self.buyer)
        response = self.client.post(
            reverse("ticket-order-list"),
            {
                "event_id": str(self.event.pk),
                "customer_name": "API Buyer",
                "customer_email": self.buyer.email,
                "referral_code": self.code.code,
                "items": [{"ticket_type_id": str(self.ticket_type.pk), "quantity": 1}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ReferralAttribution.objects.filter(order_id=response.json()["id"], partner=self.partner).exists())

    def test_inactive_campaign_code_is_not_attributed(self):
        self.campaign.status = CampaignStatus.PAUSED
        self.campaign.save(update_fields=["status", "updated_at"])
        order = self._order()
        attribution = attribute_order(order=order, referral_code=self.code)
        self.assertIsNone(attribution)

    def test_custom_referral_percentage_overrides_campaign(self):
        self.code.commission_value_override = Decimal("20.00")
        self.code.commission_type_override = CommissionType.PERCENTAGE
        self.code.save()
        order = self._order()
        attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        self.assertEqual(PartnerCommission.objects.get(order=order).amount, Decimal("20.00"))
