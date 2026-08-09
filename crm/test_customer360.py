from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationFollow, OrganizationMembership, OrganizationRole
from partners.models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    Partner,
    ReferralAttribution,
    ReferralCode,
)
from promotions.models import DiscountType, Promotion, PromotionCode, PromotionRedemption, RedemptionStatus
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)

from .customer360 import customer_360, customer_timeline, merge_behavior_filters
from .models import (
    AudienceKind,
    AudienceSegment,
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CommunicationCampaign,
    CRMContact,
)
from .selectors import audience_contacts


User = get_user_model()


class Customer360Tests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.owner = User.objects.create_user(username="c360-owner", email="owner@c360.test", password="Strong-password-2026!")
        self.marketing = User.objects.create_user(username="c360-marketing", email="marketing@c360.test", password="Strong-password-2026!")
        self.event_manager = User.objects.create_user(username="c360-events", email="events@c360.test", password="Strong-password-2026!")
        self.finance = User.objects.create_user(username="c360-finance", email="finance@c360.test", password="Strong-password-2026!")
        self.customer = User.objects.create_user(username="c360-customer", email="customer@c360.test", password="Strong-password-2026!", first_name="Aline")
        self.other = User.objects.create_user(username="c360-other", email="other@c360.test", password="Strong-password-2026!", first_name="Benoît")

        self.organization = Organization.objects.create(name="Customer 360 Events", created_by=self.owner, public_profile=True)
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.marketing, OrganizationRole.MARKETING),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
            (self.finance, OrganizationRole.FINANCE),
        ]:
            OrganizationMembership.objects.create(organization=self.organization, user=user, role=role)

        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Customer Intelligence Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=20),
            end_at=self.now + timedelta(days=20, hours=5),
            published_at=self.now,
            capacity=500,
        )
        self.past_event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Customer Intelligence Past",
            status=EventStatus.COMPLETED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now - timedelta(days=30),
            end_at=self.now - timedelta(days=30) + timedelta(hours=5),
            published_at=self.now - timedelta(days=60),
            capacity=500,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("50.00"),
            currency="USD",
            quantity_total=500,
        )
        self.past_ticket_type = TicketType.objects.create(
            event=self.past_event,
            name="Pass historique",
            price=Decimal("30.00"),
            currency="USD",
            quantity_total=500,
        )
        self.contact = CRMContact.objects.create(
            organization=self.organization,
            user=self.customer,
            email=self.customer.email,
            name=self.customer.full_name,
            first_seen_at=self.now - timedelta(days=200),
            last_seen_at=self.now,
        )
        self.other_contact = CRMContact.objects.create(
            organization=self.organization,
            user=self.other,
            email=self.other.email,
            name=self.other.full_name,
            first_seen_at=self.now - timedelta(days=200),
            last_seen_at=self.now,
        )

    def order(self, user, *, amount, currency="USD", days_ago=10, event=None, status=TicketOrderStatus.CONFIRMED):
        event = event or self.event
        return TicketOrder.objects.create(
            event=event,
            buyer=user,
            customer_name=user.full_name or user.username,
            customer_email=user.email,
            status=status,
            total_amount=Decimal(str(amount)),
            currency=currency,
            confirmed_at=self.now - timedelta(days=days_ago) if status == TicketOrderStatus.CONFIRMED else None,
        )

    def create_engagement_graph(self):
        order_recent = self.order(self.customer, amount="50.00", days_ago=10)
        order_past = self.order(self.customer, amount="30.00", days_ago=45, event=self.past_event)
        Ticket.objects.create(
            event=self.past_event,
            ticket_type=self.past_ticket_type,
            order=order_past,
            owner=self.customer,
            holder_name=self.customer.full_name,
            holder_email=self.customer.email,
            status=TicketStatus.USED,
            used_at=self.now - timedelta(days=30),
        )
        TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.customer,
            requested_quantity=1,
            status=WaitlistStatus.CONVERTED,
            converted_at=self.now - timedelta(days=8),
        )
        OrganizationFollow.objects.create(organization=self.organization, user=self.customer)

        segment = AudienceSegment.objects.create(
            organization=self.organization,
            name="Tous C360",
            audience_kind=AudienceKind.ALL,
            created_by=self.marketing,
        )
        campaign = CommunicationCampaign.objects.create(
            organization=self.organization,
            segment=segment,
            event=self.event,
            name="Relance C360",
            subject="Retournez à Makolo",
            body="Message",
            created_by=self.marketing,
        )
        recipient = CampaignRecipient.objects.create(
            campaign=campaign,
            contact=self.contact,
            user=self.customer,
            email=self.customer.email,
            name=self.customer.full_name,
            status=CampaignRecipientStatus.SENT,
            sent_at=self.now - timedelta(days=7),
            click_count=2,
            first_clicked_at=self.now - timedelta(days=6),
            last_clicked_at=self.now - timedelta(days=5),
        )
        CampaignAttribution.objects.create(
            order=order_recent,
            campaign=campaign,
            recipient=recipient,
            contact=self.contact,
            status=CampaignAttributionStatus.CONFIRMED,
            revenue_amount=order_recent.total_amount,
            currency="USD",
            captured_at=self.now - timedelta(days=6),
            confirmed_at=self.now - timedelta(days=5),
        )

        promotion = Promotion.objects.create(
            organization=self.organization,
            event=self.event,
            name="C360 Promo",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("10.00"),
            currency="USD",
            created_by=self.marketing,
        )
        code = PromotionCode.objects.create(
            promotion=promotion,
            code="C360PROMO",
            created_by=self.marketing,
        )
        PromotionRedemption.objects.create(
            promotion=promotion,
            code=code,
            order=order_recent,
            buyer=self.customer,
            customer_email=self.customer.email,
            status=RedemptionStatus.CONFIRMED,
            subtotal_amount=Decimal("55.00"),
            eligible_amount=Decimal("50.00"),
            discount_amount=Decimal("5.00"),
            final_amount=Decimal("50.00"),
            currency="USD",
            confirmed_at=self.now - timedelta(days=5),
        )

        partner = Partner.objects.create(
            organization=self.organization,
            name="Ambassadeur C360",
            created_by=self.marketing,
        )
        affiliate = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.past_event,
            name="Acquisition C360",
            status=CampaignStatus.ACTIVE,
            created_by=self.marketing,
        )
        referral_code = ReferralCode.objects.create(
            campaign=affiliate,
            partner=partner,
            code="C360REF",
        )
        ReferralAttribution.objects.create(
            order=order_past,
            referral_code=referral_code,
            campaign=affiliate,
            partner=partner,
            status=AttributionStatus.CONFIRMED,
            confirmed_at=self.now - timedelta(days=29),
        )

        transfer_ticket = Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=order_recent,
            owner=self.other,
            holder_name=self.other.full_name,
            holder_email=self.other.email,
            status=TicketStatus.VALID,
        )
        TicketTransfer.objects.create(
            ticket=transfer_ticket,
            sender=self.customer,
            recipient=self.other,
            recipient_email=self.other.email,
            status=TransferStatus.ACCEPTED,
            expires_at=self.now + timedelta(days=1),
            accepted_at=self.now - timedelta(days=4),
        )
        return order_recent, order_past

    def test_customer_360_aggregates_cross_domain_activity(self):
        self.create_engagement_graph()
        summary = customer_360(self.contact, include_financials=True)

        self.assertEqual(summary["orders"]["confirmed"], 2)
        self.assertEqual(summary["orders"]["distinct_events"], 2)
        self.assertEqual(summary["tickets"]["attended_events"], 1)
        self.assertEqual(summary["waitlist"]["converted"], 1)
        self.assertEqual(summary["transfers"]["accepted"], 1)
        self.assertEqual(summary["engagement"]["campaigns_clicked"], 1)
        self.assertEqual(summary["engagement"]["campaign_conversions"], 1)
        self.assertEqual(summary["engagement"]["promotion_redemptions"], 1)
        self.assertEqual(summary["engagement"]["partner_referred_orders"], 1)
        self.assertTrue(summary["engagement"]["follows_organization"])
        self.assertEqual(summary["financial"]["spend_by_currency"][0]["amount"], Decimal("80.00"))
        self.assertGreater(summary["rfm"]["recency_score"], 0)
        self.assertGreater(summary["rfm"]["frequency_score"], 0)

    def test_financial_customer_360_is_explicitly_optional(self):
        self.order(self.customer, amount="99.00", days_ago=3)
        hidden = customer_360(self.contact, include_financials=False)
        visible = customer_360(self.contact, include_financials=True)

        self.assertIsNone(hidden["financial"])
        self.assertFalse(hidden["rfm"]["monetary_visible"])
        self.assertEqual(hidden["rfm"]["monetary_by_currency"], [])
        self.assertIsNotNone(visible["financial"])
        self.assertTrue(visible["rfm"]["monetary_visible"])

    def test_spend_and_monetary_scores_never_mix_currencies(self):
        self.order(self.customer, amount="50.00", currency="USD", days_ago=5)
        self.order(self.customer, amount="10000.00", currency="CDF", days_ago=4)
        summary = customer_360(self.contact, include_financials=True)
        rows = {row["currency"]: row for row in summary["financial"]["spend_by_currency"]}

        self.assertEqual(rows["USD"]["amount"], Decimal("50.00"))
        self.assertEqual(rows["CDF"]["amount"], Decimal("10000.00"))
        self.assertIn(rows["USD"]["monetary_score"], {1, 2, 3, 4, 5})
        self.assertIn(rows["CDF"]["monetary_score"], {1, 2, 3, 4, 5})

    def test_timeline_hides_financial_metadata_when_not_authorized(self):
        self.create_engagement_graph()
        timeline = customer_timeline(self.contact, include_financials=False)
        kinds = {item["kind"] for item in timeline}

        self.assertIn("order", kinds)
        self.assertIn("checkin", kinds)
        self.assertIn("campaign_click", kinds)
        self.assertIn("promotion", kinds)
        self.assertIn("partner", kinds)
        self.assertTrue(all("amount" not in item["metadata"] for item in timeline))
        self.assertTrue(all("discount_amount" not in item["metadata"] for item in timeline))

    def test_customer_360_web_respects_individual_financial_boundary(self):
        self.order(self.customer, amount="87.65", days_ago=2)

        self.client.force_login(self.owner)
        owner_response = self.client.get(reverse("crm:contact-detail", kwargs={"pk": self.contact.pk}))
        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, "RFM complet")
        self.assertContains(owner_response, "87.65")

        self.client.force_login(self.marketing)
        marketing_response = self.client.get(reverse("crm:contact-detail", kwargs={"pk": self.contact.pk}))
        self.assertEqual(marketing_response.status_code, 200)
        self.assertContains(marketing_response, "montants individuels")
        self.assertNotContains(marketing_response, "87.65")

    def test_behavioral_segment_filters_repeat_buyers(self):
        self.order(self.customer, amount="20.00", days_ago=10)
        self.order(self.customer, amount="20.00", days_ago=20)
        self.order(self.other, amount="20.00", days_ago=10)
        segment = AudienceSegment.objects.create(
            organization=self.organization,
            name="Récurrents",
            audience_kind=AudienceKind.ALL,
            custom_filters=merge_behavior_filters({}, {"min_confirmed_orders": 2}),
            created_by=self.marketing,
        )

        ids = set(audience_contacts(segment).values_list("id", flat=True))
        self.assertIn(self.contact.pk, ids)
        self.assertNotIn(self.other_contact.pk, ids)

    def test_behavioral_segment_combines_recency_and_lapsed_windows(self):
        self.order(self.customer, amount="20.00", days_ago=200)
        self.order(self.other, amount="20.00", days_ago=20)
        lapsed = AudienceSegment.objects.create(
            organization=self.organization,
            name="À réactiver",
            audience_kind=AudienceKind.ALL,
            custom_filters=merge_behavior_filters({}, {"min_days_since_last_order": 180}),
            created_by=self.marketing,
        )
        active = AudienceSegment.objects.create(
            organization=self.organization,
            name="Actifs",
            audience_kind=AudienceKind.ALL,
            custom_filters=merge_behavior_filters({}, {"max_days_since_last_order": 30}),
            created_by=self.marketing,
        )

        self.assertEqual(list(audience_contacts(lapsed).values_list("id", flat=True)), [self.contact.pk])
        self.assertEqual(list(audience_contacts(active).values_list("id", flat=True)), [self.other_contact.pk])

    def test_behavioral_segment_filters_attendance_and_spend_in_one_currency(self):
        customer_order = self.order(self.customer, amount="80.00", days_ago=10, event=self.past_event)
        other_order = self.order(self.other, amount="100000.00", currency="CDF", days_ago=10, event=self.past_event)
        Ticket.objects.create(
            event=self.past_event,
            ticket_type=self.past_ticket_type,
            order=customer_order,
            owner=self.customer,
            holder_name=self.customer.full_name,
            holder_email=self.customer.email,
            status=TicketStatus.USED,
            used_at=self.now - timedelta(days=9),
        )
        Ticket.objects.create(
            event=self.past_event,
            ticket_type=self.past_ticket_type,
            order=other_order,
            owner=self.other,
            holder_name=self.other.full_name,
            holder_email=self.other.email,
            status=TicketStatus.USED,
            used_at=self.now - timedelta(days=9),
        )
        segment = AudienceSegment.objects.create(
            organization=self.organization,
            name="VIP présents",
            audience_kind=AudienceKind.ALL,
            custom_filters=merge_behavior_filters(
                {},
                {
                    "min_attended_events": 1,
                    "min_spend_amount": "70.00",
                    "spend_currency": "USD",
                },
            ),
            created_by=self.marketing,
        )

        ids = set(audience_contacts(segment).values_list("id", flat=True))
        self.assertEqual(ids, {self.contact.pk})

    def test_segment_web_form_persists_behavior_namespace_without_polluting_custom_fields(self):
        self.client.force_login(self.marketing)
        response = self.client.post(
            reverse("crm:segment-create", kwargs={"slug": self.organization.slug}),
            data={
                "name": "Clients récents premium",
                "description": "Lot 3",
                "audience_kind": AudienceKind.ALL,
                "marketing_consent_only": "",
                "city": "",
                "country": "",
                "custom_filters": '{"niveau":"vip"}',
                "min_confirmed_orders": "2",
                "max_days_since_last_order": "90",
                "min_spend_amount": "100.00",
                "spend_currency": "usd",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        segment = AudienceSegment.objects.get(name="Clients récents premium")
        self.assertEqual(segment.custom_filters["niveau"], "vip")
        self.assertEqual(segment.custom_filters["$behavior"]["min_confirmed_orders"], 2)
        self.assertEqual(segment.custom_filters["$behavior"]["spend_currency"], "USD")

    def test_customer_360_api_hides_financials_from_marketing_and_denies_finance_crm_access(self):
        self.order(self.customer, amount="55.00", days_ago=5)
        url = f"/api/v1/crm/contacts/{self.contact.pk}/360/"

        self.client.force_login(self.marketing)
        marketing = self.client.get(url)
        self.assertEqual(marketing.status_code, 200, marketing.content)
        self.assertFalse(marketing.json()["financials_visible"])
        self.assertIsNone(marketing.json()["summary"]["financial"])

        self.client.force_login(self.finance)
        finance = self.client.get(url)
        self.assertEqual(finance.status_code, 404)

    def test_behavioral_segment_api_uses_business_permissions(self):
        payload = {
            "organization_id": str(self.organization.pk),
            "name": "API récurrents",
            "audience_kind": AudienceKind.ALL,
            "behavior_filters": {"min_confirmed_orders": 2, "max_days_since_last_order": 90},
        }

        self.client.force_login(self.event_manager)
        denied = self.client.post(
            "/api/v1/crm/segments/behavioral/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403, denied.content)

        self.client.force_login(self.marketing)
        allowed = self.client.post(
            "/api/v1/crm/segments/behavioral/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 201, allowed.content)
        self.assertEqual(allowed.json()["behavior_filters"]["min_confirmed_orders"], 2)
