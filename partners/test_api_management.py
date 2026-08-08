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

from .models import AffiliateCampaign, CampaignStatus, CommissionType, Partner, PartnerCommission, ReferralAttribution, ReferralCode
from .services import attribute_order


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PartnerManagementAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="api-partner-owner", email="api-owner@example.com", password="Strong-password-2026!", is_verified=True)
        self.marketing = User.objects.create_user(username="api-partner-marketing", email="api-marketing@example.com", password="Strong-password-2026!", is_verified=True)
        self.finance = User.objects.create_user(username="api-partner-finance", email="api-finance@example.com", password="Strong-password-2026!", is_verified=True)
        self.buyer = User.objects.create_user(username="api-partner-buyer", email="api-buyer@example.com", password="Strong-password-2026!", is_verified=True)
        self.organization = Organization.objects.create(name="API Partner Org", created_by=self.owner)
        for user, role in ((self.owner, OrganizationRole.OWNER), (self.marketing, OrganizationRole.MARKETING), (self.finance, OrganizationRole.FINANCE)):
            OrganizationMembership.objects.create(organization=self.organization, user=user, role=role)
        start = timezone.now() + timedelta(days=12)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="API Affiliate Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            published_at=timezone.now(),
        )
        self.ticket_type = TicketType.objects.create(event=self.event, name="Standard", price=Decimal("40.00"), currency="USD", quantity_total=50)

    def test_marketing_can_create_partner_campaign_and_code_via_api(self):
        self.client.force_login(self.marketing)
        partner_response = self.client.post(
            reverse("partners_api:partners"),
            {
                "organization_id": str(self.organization.pk),
                "name": "API Creator",
                "kind": "influencer",
                "email": "creator-api@example.com",
            },
            content_type="application/json",
        )
        self.assertEqual(partner_response.status_code, 201)
        partner_id = partner_response.json()["id"]

        campaign_response = self.client.post(
            reverse("partners_api:campaigns"),
            {
                "organization_id": str(self.organization.pk),
                "event_id": str(self.event.pk),
                "name": "API Launch",
                "status": CampaignStatus.ACTIVE,
                "commission_type": CommissionType.PERCENTAGE,
                "commission_value": "8.00",
                "commission_currency": "USD",
                "attribution_window_days": 21,
            },
            content_type="application/json",
        )
        self.assertEqual(campaign_response.status_code, 201)
        campaign_id = campaign_response.json()["id"]

        code_response = self.client.post(
            reverse("partners_api:codes"),
            {"campaign_id": campaign_id, "partner_id": partner_id, "code": "APICREATOR8"},
            content_type="application/json",
        )
        self.assertEqual(code_response.status_code, 201)
        self.assertEqual(code_response.json()["code"], "APICREATOR8")

    def test_finance_cannot_create_marketing_campaign_via_api(self):
        self.client.force_login(self.finance)
        response = self.client.post(
            reverse("partners_api:campaigns"),
            {
                "organization_id": str(self.organization.pk),
                "event_id": str(self.event.pk),
                "name": "Forbidden Finance Campaign",
                "status": CampaignStatus.ACTIVE,
                "commission_type": CommissionType.PERCENTAGE,
                "commission_value": "5.00",
                "commission_currency": "USD",
                "attribution_window_days": 30,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_finance_can_create_and_complete_payout_via_api(self):
        partner = Partner.objects.create(organization=self.organization, name="Payout Partner", email="payout@example.com", created_by=self.owner)
        campaign = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            name="Payout Campaign",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            created_by=self.owner,
        )
        code = ReferralCode.objects.create(campaign=campaign, partner=partner, code="PAYOUT10")
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="API Buyer",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        attribute_order(order=order, referral_code=code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        self.assertEqual(PartnerCommission.objects.get(order=order).amount, Decimal("4.00"))

        self.client.force_login(self.finance)
        response = self.client.post(
            reverse("partners_api:payouts"),
            {"partner_id": str(partner.pk), "currency": "USD", "reference": "API-PAYOUT"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payout_id = response.json()["id"]
        paid_response = self.client.post(
            reverse("partners_api:payout-paid", kwargs={"pk": payout_id}),
            {"reference": "BANK-API-001"},
            content_type="application/json",
        )
        self.assertEqual(paid_response.status_code, 200)
        self.assertEqual(paid_response.json()["status"], "paid")

    def test_marketing_cannot_create_payout(self):
        partner = Partner.objects.create(organization=self.organization, name="No Payout", created_by=self.owner)
        self.client.force_login(self.marketing)
        response = self.client.post(
            reverse("partners_api:payouts"),
            {"partner_id": str(partner.pk), "currency": "USD"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
