from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from organizations.services import follow_organization
from tickets.models import TicketOrder, TicketOrderStatus, TicketType

from .models import (
    AudienceKind,
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignTemplate,
    CommunicationCampaignStatus,
    CommunicationKind,
    CRMContact,
    CustomFieldType,
    MarketingConsent,
)
from .selectors import audience_contacts, campaign_metrics
from .services import (
    assign_contact_tag,
    campaign_click_token,
    create_campaign,
    create_campaign_template,
    create_custom_field,
    create_segment,
    create_tag,
    set_contact_custom_value,
    set_marketing_consent,
    sync_contact_from_follower,
)


User = get_user_model()


class CRMDataModelGrowthTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="growth-owner", email="growth-owner@example.com", password="Strong-password-2026!")
        self.marketing = User.objects.create_user(username="growth-marketing", email="growth-marketing@example.com", password="Strong-password-2026!")
        self.finance = User.objects.create_user(username="growth-finance", email="growth-finance@example.com", password="Strong-password-2026!")
        self.customer = User.objects.create_user(username="growth-customer", email="growth-customer@example.com", password="Strong-password-2026!", first_name="Grâce")
        self.organization = Organization.objects.create(name="Growth Events", created_by=self.owner, public_profile=True)
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationRole.OWNER)
        OrganizationMembership.objects.create(organization=self.organization, user=self.marketing, role=OrganizationRole.MARKETING)
        OrganizationMembership.objects.create(organization=self.organization, user=self.finance, role=OrganizationRole.FINANCE)
        start = timezone.now() + timedelta(days=10)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Growth Festival",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=5),
            published_at=timezone.now(),
            capacity=200,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=200,
        )
        self.contact = CRMContact.objects.create(
            organization=self.organization,
            user=self.customer,
            email=self.customer.email,
            name=self.customer.full_name,
            marketing_consent=MarketingConsent.SUBSCRIBED,
            consent_source="test-opt-in",
            consent_updated_at=timezone.now(),
        )

    def test_follower_segment_is_dynamic(self):
        with self.captureOnCommitCallbacks(execute=True):
            follow = follow_organization(user=self.customer, organization=self.organization)
        sync_contact_from_follower(follow)
        segment = create_segment(
            organization=self.organization,
            actor=self.marketing,
            name="Communauté",
            audience_kind=AudienceKind.FOLLOWERS,
        )
        self.assertEqual(list(audience_contacts(segment).values_list("email", flat=True)), [self.customer.email])

    def test_tags_and_custom_fields_combine_in_dynamic_segment(self):
        vip = create_tag(organization=self.organization, actor=self.marketing, name="VIP")
        assign_contact_tag(contact=self.contact, tag=vip, actor=self.marketing)
        level = create_custom_field(
            organization=self.organization,
            actor=self.marketing,
            key="niveau",
            label="Niveau relation",
            field_type=CustomFieldType.SELECT,
            options=["standard", "premium"],
        )
        set_contact_custom_value(contact=self.contact, field=level, actor=self.marketing, value="premium")
        segment = create_segment(
            organization=self.organization,
            actor=self.marketing,
            name="VIP premium",
            audience_kind=AudienceKind.ALL,
            required_tags=[vip],
            custom_filters={"niveau": "premium"},
        )
        self.assertEqual(audience_contacts(segment).count(), 1)
        set_contact_custom_value(contact=self.contact, field=level, actor=self.marketing, value="standard")
        self.assertEqual(audience_contacts(segment).count(), 0)

    def test_invalid_select_custom_value_is_rejected(self):
        field = create_custom_field(
            organization=self.organization,
            actor=self.marketing,
            key="niveau",
            label="Niveau",
            field_type=CustomFieldType.SELECT,
            options=["vip"],
        )
        with self.assertRaises(ValidationError):
            set_contact_custom_value(contact=self.contact, field=field, actor=self.marketing, value="inconnu")

    def test_finance_cannot_create_marketing_configuration(self):
        with self.assertRaises(PermissionDenied):
            create_tag(organization=self.organization, actor=self.finance, name="Finance")
        with self.assertRaises(PermissionDenied):
            create_campaign_template(
                organization=self.organization,
                actor=self.finance,
                name="Finance template",
                kind=CommunicationKind.MARKETING,
                subject="No",
                body="No",
            )

    def test_campaign_template_is_reused_and_counted(self):
        template = create_campaign_template(
            organization=self.organization,
            actor=self.marketing,
            name="Nouvel événement",
            kind=CommunicationKind.MARKETING,
            subject="Découvrez notre prochain événement",
            body="Une nouvelle expérience vous attend.",
            cta_label="Découvrir",
            cta_url="https://example.com/events",
        )
        segment = create_segment(
            organization=self.organization,
            actor=self.marketing,
            name="Tous opt-in",
            audience_kind=AudienceKind.ALL,
            marketing_consent_only=True,
        )
        campaign = create_campaign(
            organization=self.organization,
            actor=self.marketing,
            segment=segment,
            template=template,
            name="Édition août",
            kind="",
            subject="",
            body="",
        )
        template.refresh_from_db()
        self.assertEqual(campaign.subject, template.subject)
        self.assertEqual(campaign.body, template.body)
        self.assertEqual(campaign.cta_url, template.cta_url)
        self.assertEqual(template.use_count, 1)

    def test_manual_org_consent_does_not_mutate_global_account_preference(self):
        preference = NotificationPreference.objects.create(user=self.customer, marketing_notifications=False)
        set_marketing_consent(contact=self.contact, actor=self.marketing, subscribed=True, source="organization-form")
        preference.refresh_from_db()
        self.assertFalse(preference.marketing_notifications)


class CampaignSalesAttributionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="attr-owner", email="attr-owner@example.com", password="Strong-password-2026!")
        self.marketing = User.objects.create_user(username="attr-marketing", email="attr-marketing@example.com", password="Strong-password-2026!")
        self.customer = User.objects.create_user(username="attr-customer", email="attr-customer@example.com", password="Strong-password-2026!")
        self.organization = Organization.objects.create(name="Attribution Events", created_by=self.owner, public_profile=True)
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationRole.OWNER)
        OrganizationMembership.objects.create(organization=self.organization, user=self.marketing, role=OrganizationRole.MARKETING)
        start = timezone.now() + timedelta(days=8)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Conversion Show",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            published_at=timezone.now(),
            capacity=100,
        )
        self.ticket_type = TicketType.objects.create(event=self.event, name="Paid", price=Decimal("30.00"), currency="USD", quantity_total=100)
        self.contact = CRMContact.objects.create(
            organization=self.organization,
            user=self.customer,
            email=self.customer.email,
            marketing_consent=MarketingConsent.SUBSCRIBED,
            consent_source="test",
            consent_updated_at=timezone.now(),
        )
        self.segment = create_segment(
            organization=self.organization,
            actor=self.marketing,
            name="Audience attribution",
            audience_kind=AudienceKind.ALL,
            marketing_consent_only=True,
        )
        self.campaign = create_campaign(
            organization=self.organization,
            actor=self.marketing,
            segment=self.segment,
            event=self.event,
            name="Conversion août",
            kind=CommunicationKind.MARKETING,
            subject="Réservez",
            body="Votre place vous attend.",
            cta_label="Réserver",
            cta_url=f"http://testserver/tickets/buy/{self.event.slug}/",
            track_conversions=True,
            attribution_window_days=30,
        )
        self.campaign.status = CommunicationCampaignStatus.SENT
        self.campaign.started_at = timezone.now()
        self.campaign.completed_at = timezone.now()
        self.campaign.save(update_fields=["status", "started_at", "completed_at", "updated_at"])
        self.recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            user=self.customer,
            email=self.customer.email,
            status=CampaignRecipientStatus.SENT,
            sent_at=timezone.now(),
        )

    def _click(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("crm:campaign-click", kwargs={"token": campaign_click_token(self.recipient)}))
        self.assertEqual(response.status_code, 302)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.click_count, 1)

    def test_web_click_then_paid_order_creates_pending_attribution_and_confirmation_promotes_it(self):
        self._click()
        response = self.client.post(
            reverse("tickets:order-create", kwargs={"event_slug": self.event.slug}),
            {
                "customer_name": "Client Attribution",
                "customer_email": self.customer.email,
                f"quantity_{self.ticket_type.pk}": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = TicketOrder.objects.filter(buyer=self.customer, event=self.event).latest("created_at")
        attribution = CampaignAttribution.objects.get(order=order)
        self.assertEqual(attribution.status, CampaignAttributionStatus.PENDING)

        order.status = TicketOrderStatus.CONFIRMED
        order.confirmed_at = timezone.now()
        order.save(update_fields=["status", "confirmed_at", "updated_at"])
        attribution.refresh_from_db()
        self.assertEqual(attribution.status, CampaignAttributionStatus.CONFIRMED)
        self.assertEqual(attribution.revenue_amount, Decimal("30.00"))
        self.assertEqual(attribution.currency, "USD")

    def test_cancelled_order_reverses_confirmed_attribution(self):
        order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.customer,
            customer_name="Client",
            customer_email=self.customer.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("30.00"),
            currency="USD",
            confirmed_at=timezone.now(),
        )
        attribution = CampaignAttribution.objects.create(
            order=order,
            campaign=self.campaign,
            recipient=self.recipient,
            contact=self.contact,
            status=CampaignAttributionStatus.CONFIRMED,
            revenue_amount=Decimal("30.00"),
            currency="USD",
            confirmed_at=timezone.now(),
        )
        order.status = TicketOrderStatus.CANCELLED
        order.cancelled_at = timezone.now()
        order.save(update_fields=["status", "cancelled_at", "updated_at"])
        attribution.refresh_from_db()
        self.assertEqual(attribution.status, CampaignAttributionStatus.REVERSED)
        self.assertIsNotNone(attribution.reversed_at)

    def test_metrics_keep_campaign_revenue_separated_by_currency(self):
        second_event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="CDF Show",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=9),
            end_at=timezone.now() + timedelta(days=9, hours=4),
        )
        self.campaign.event = None
        self.campaign.save(update_fields=["event", "updated_at"])
        for event, amount, currency in [
            (self.event, Decimal("30.00"), "USD"),
            (second_event, Decimal("50000.00"), "CDF"),
        ]:
            order = TicketOrder.objects.create(
                event=event,
                buyer=self.customer,
                customer_name="Client",
                customer_email=self.customer.email,
                status=TicketOrderStatus.CONFIRMED,
                total_amount=amount,
                currency=currency,
                confirmed_at=timezone.now(),
            )
            CampaignAttribution.objects.create(
                order=order,
                campaign=self.campaign,
                recipient=self.recipient,
                contact=self.contact,
                status=CampaignAttributionStatus.CONFIRMED,
                revenue_amount=amount,
                currency=currency,
                confirmed_at=timezone.now(),
            )
        rows = campaign_metrics(self.campaign)["revenue_by_currency"]
        self.assertEqual({row["currency"] for row in rows}, {"USD", "CDF"})

    def test_invalid_campaign_click_returns_404(self):
        response = self.client.get(reverse("crm:campaign-click", kwargs={"token": "not-a-valid-token"}))
        self.assertEqual(response.status_code, 404)

    def test_api_campaign_token_attributes_free_order(self):
        free_type = TicketType.objects.create(event=self.event, name="Free", price=0, currency="USD", quantity_total=20)
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("ticket-orders-list"),
            {
                "event_id": str(self.event.pk),
                "customer_name": "API Client",
                "customer_email": self.customer.email,
                "campaign_token": campaign_click_token(self.recipient),
                "items": [{"ticket_type_id": str(free_type.pk), "quantity": 1}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        order = TicketOrder.objects.get(pk=response.json()["id"])
        attribution = CampaignAttribution.objects.get(order=order)
        self.assertEqual(attribution.status, CampaignAttributionStatus.CONFIRMED)
