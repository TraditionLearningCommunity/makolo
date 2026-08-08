from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from payments.models import PaymentMethod, PaymentProvider
from payments.services import complete_sandbox_payment, initiate_payment
from tickets.models import TicketType
from tickets.services import create_order

from .models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    CommissionType,
    Partner,
    PartnerCommission,
    PartnerStatus,
    ReferralAttribution,
    ReferralCode,
)
from .services import attribute_order


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class AffiliationIntegrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="aff-owner-2",
            email="aff-owner-2@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.marketing = User.objects.create_user(
            username="aff-marketing-2",
            email="aff-marketing-2@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.finance = User.objects.create_user(
            username="aff-finance-2",
            email="aff-finance-2@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.ambassador = User.objects.create_user(
            username="aff-ambassador-2",
            email="aff-ambassador-2@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.buyer = User.objects.create_user(
            username="aff-buyer-2",
            email="aff-buyer-2@example.com",
            password="Strong-password-2026!",
            is_verified=True,
        )
        self.organization = Organization.objects.create(
            name="Affiliate Integration Org",
            created_by=self.owner,
        )
        for user, role in (
            (self.owner, OrganizationRole.OWNER),
            (self.marketing, OrganizationRole.MARKETING),
            (self.finance, OrganizationRole.FINANCE),
        ):
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )
        start = timezone.now() + timedelta(days=10)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Affiliate Intelligence Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=3),
            published_at=timezone.now(),
            capacity=200,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Paid",
            price=Decimal("50.00"),
            currency="USD",
            quantity_total=200,
        )
        self.partner = Partner.objects.create(
            organization=self.organization,
            user=self.ambassador,
            name="Ambassador Integration",
            email=self.ambassador.email,
            status=PartnerStatus.ACTIVE,
            created_by=self.owner,
        )
        self.campaign = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            name="Integration Campaign",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("12.00"),
            commission_currency="USD",
            created_by=self.owner,
        )
        self.code = ReferralCode.objects.create(
            campaign=self.campaign,
            partner=self.partner,
            code="INTEGRATE12",
        )

    def _create_and_pay(self, buyer=None):
        buyer = buyer or self.buyer
        order = create_order(
            buyer=buyer,
            event=self.event,
            customer_name=buyer.full_name or buyer.username,
            customer_email=buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        attribution = attribute_order(order=order, referral_code=self.code)
        payment = initiate_payment(
            order=order,
            actor=buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )
        complete_sandbox_payment(payment=payment, actor=buyer)
        return order, attribution

    def test_self_referral_is_quarantined_without_breaking_checkout(self):
        order, attribution = self._create_and_pay(buyer=self.ambassador)
        attribution.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(attribution.status, AttributionStatus.REVERSED)
        self.assertFalse(PartnerCommission.objects.filter(attribution=attribution).exists())

    def test_marketing_can_edit_campaign_but_finance_cannot(self):
        self.client.force_login(self.marketing)
        response = self.client.post(
            reverse("partners:campaign-edit", kwargs={"pk": self.campaign.pk}),
            {
                "event": str(self.event.pk),
                "name": "Updated Campaign",
                "status": CampaignStatus.PAUSED,
                "commission_type": CommissionType.PERCENTAGE,
                "commission_value": "15.00",
                "commission_currency": "USD",
                "attribution_window_days": "14",
                "starts_at": "",
                "ends_at": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.name, "Updated Campaign")
        self.assertEqual(self.campaign.status, CampaignStatus.PAUSED)

        self.client.force_login(self.finance)
        response = self.client.get(reverse("partners:campaign-edit", kwargs={"pk": self.campaign.pk}))
        self.assertEqual(response.status_code, 403)

    def test_marketing_can_disable_referral_code(self):
        self.client.force_login(self.marketing)
        response = self.client.post(reverse("partners:referral-toggle", kwargs={"pk": self.code.pk}))
        self.assertEqual(response.status_code, 302)
        self.code.refresh_from_db()
        self.assertFalse(self.code.is_active)

    def test_event_analytics_include_partner_acquisition_without_buyer_pii(self):
        self.client.get(reverse("partners:referral-landing", kwargs={"code": self.code.code}))
        self._create_and_pay()

        self.client.force_login(self.marketing)
        response = self.client.get(reverse("analytics_api:event-detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["partners"]["confirmed_orders"], 1)
        self.assertEqual(payload["partners"]["visits"], 1)
        self.assertEqual(payload["partners"]["commission_totals"], [])
        serialized = str(payload)
        self.assertNotIn(self.buyer.email, serialized)
        self.assertNotIn(self.buyer.username, serialized)

    def test_finance_event_analytics_include_commission_totals_by_currency(self):
        self._create_and_pay()
        self.client.force_login(self.finance)
        response = self.client.get(reverse("analytics_api:event-detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        partner_data = response.json()["partners"]
        self.assertTrue(partner_data["financial_visible"])
        self.assertEqual(partner_data["commission_totals"][0]["currency"], "USD")
        self.assertEqual(Decimal(partner_data["commission_totals"][0]["earned"]), Decimal("6.00"))
