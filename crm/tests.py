from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from events.models import Event, EventStatus, EventVisibility
from notifications.models import Notification
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus, TicketType

from .models import (
    AudienceKind,
    AudienceSegment,
    CampaignRecipient,
    CampaignRecipientStatus,
    CommunicationCampaign,
    CommunicationCampaignStatus,
    CommunicationKind,
    CRMContact,
    MarketingConsent,
)
from .selectors import audience_contacts
from .services import (
    campaign_unsubscribe_token,
    create_campaign,
    create_segment,
    launch_campaign,
    process_due_campaigns,
    schedule_campaign,
    set_marketing_consent,
    unsubscribe_from_token,
)


User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EventCRMTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="crm-owner", email="crm-owner@example.com", password="Strong-password-2026!", is_verified=True)
        self.marketing = User.objects.create_user(username="crm-marketing", email="crm-marketing@example.com", password="Strong-password-2026!", is_verified=True)
        self.event_manager = User.objects.create_user(username="crm-event", email="crm-event@example.com", password="Strong-password-2026!", is_verified=True)
        self.finance = User.objects.create_user(username="crm-finance", email="crm-finance@example.com", password="Strong-password-2026!", is_verified=True)
        self.attendee = User.objects.create_user(username="crm-attendee", email="attendee@example.com", password="Strong-password-2026!", is_verified=True, first_name="Aline", last_name="Participant")
        self.organization = Organization.objects.create(name="Makolo CRM Lab", created_by=self.owner)
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.marketing, OrganizationRole.MARKETING),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
            (self.finance, OrganizationRole.FINANCE),
        ]:
            OrganizationMembership.objects.create(organization=self.organization, user=user, role=role)
        start = timezone.now() + timedelta(days=7)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="CRM Summit",
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
            price=Decimal("20.00"),
            currency="USD",
            quantity_total=100,
        )

    def _order(self, *, user=None, email=None, status=TicketOrderStatus.CONFIRMED):
        user = user if user is not None else self.attendee
        email = email or user.email
        return TicketOrder.objects.create(
            event=self.event,
            buyer=user,
            customer_name=user.full_name,
            customer_email=email,
            status=status,
            total_amount=Decimal("20.00"),
            currency="USD",
            confirmed_at=timezone.now() if status == TicketOrderStatus.CONFIRMED else None,
        )

    def _ticket(self, *, guest=False, email=None, status=TicketStatus.VALID, event=None, ticket_type=None):
        event = event or self.event
        ticket_type = ticket_type or self.ticket_type
        user = None if guest else self.attendee
        email = email or (user.email if user else "guest@example.com")
        name = user.full_name if user else "Guest Contact"
        order = TicketOrder.objects.create(
            event=event,
            buyer=user,
            customer_name=name,
            customer_email=email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=ticket_type.price,
            currency=ticket_type.currency,
            confirmed_at=timezone.now(),
        )
        return Ticket.objects.create(
            event=event,
            ticket_type=ticket_type,
            order=order,
            owner=user,
            holder_name=name,
            holder_email=email,
            status=status,
            used_at=timezone.now() if status == TicketStatus.USED else None,
        )

    def test_ticket_order_sync_creates_contact_without_implicit_marketing_opt_in(self):
        self._order()
        contact = CRMContact.objects.get(organization=self.organization, email=self.attendee.email)
        self.assertEqual(contact.marketing_consent, MarketingConsent.UNKNOWN)
        self.assertEqual(contact.user, self.attendee)

    def test_account_marketing_preference_can_seed_positive_consent(self):
        NotificationPreference.objects.create(user=self.attendee, marketing_notifications=True)
        self._order()
        contact = CRMContact.objects.get(organization=self.organization, email=self.attendee.email)
        self.assertEqual(contact.marketing_consent, MarketingConsent.SUBSCRIBED)
        self.assertEqual(contact.consent_source, "account_notification_preferences")

    def test_finance_cannot_manage_crm_but_marketing_can(self):
        segment = create_segment(organization=self.organization, actor=self.marketing, name="Tous", audience_kind=AudienceKind.ALL)
        self.assertEqual(segment.organization, self.organization)
        with self.assertRaises(PermissionDenied):
            create_segment(organization=self.organization, actor=self.finance, name="Finance segment", audience_kind=AudienceKind.ALL)

    def test_confirmed_buyer_segment_is_derived_from_ticket_orders(self):
        self._order()
        segment = AudienceSegment.objects.create(organization=self.organization, event=self.event, name="Acheteurs", audience_kind=AudienceKind.CONFIRMED_BUYERS, created_by=self.marketing)
        self.assertEqual(list(audience_contacts(segment).values_list("email", flat=True)), [self.attendee.email])

    def test_attendee_segment_is_derived_from_used_ticket(self):
        self._ticket(status=TicketStatus.USED)
        segment = AudienceSegment.objects.create(organization=self.organization, event=self.event, name="Présents", audience_kind=AudienceKind.ATTENDEES, created_by=self.marketing)
        self.assertEqual(audience_contacts(segment).count(), 1)

    def test_no_show_segment_only_activates_after_event_end(self):
        self._ticket(status=TicketStatus.VALID)
        segment = AudienceSegment.objects.create(organization=self.organization, event=self.event, name="No shows futurs", audience_kind=AudienceKind.NO_SHOWS, created_by=self.marketing)
        self.assertEqual(audience_contacts(segment).count(), 0)
        past = Event.objects.create(organizer=self.owner, organization=self.organization, title="Past CRM Event", status=EventStatus.COMPLETED, visibility=EventVisibility.PUBLIC, start_at=timezone.now() - timedelta(days=2), end_at=timezone.now() - timedelta(days=1), capacity=20)
        past_type = TicketType.objects.create(event=past, name="Past", price=0, currency="USD", quantity_total=20)
        self._ticket(status=TicketStatus.VALID, event=past, ticket_type=past_type)
        past_segment = AudienceSegment.objects.create(organization=self.organization, event=past, name="No shows passés", audience_kind=AudienceKind.NO_SHOWS, created_by=self.marketing)
        self.assertEqual(audience_contacts(past_segment).count(), 1)

    def test_marketing_campaign_skips_contact_without_consent(self):
        self._order()
        segment = AudienceSegment.objects.create(organization=self.organization, name="Tous contacts", audience_kind=AudienceKind.ALL, created_by=self.marketing)
        campaign = create_campaign(organization=self.organization, actor=self.marketing, segment=segment, name="Newsletter", kind=CommunicationKind.MARKETING, subject="Actualités Makolo", body="Bonjour")
        launch_campaign(campaign=campaign, actor=self.marketing)
        process_due_campaigns()
        recipient = CampaignRecipient.objects.get(campaign=campaign)
        self.assertEqual(recipient.status, CampaignRecipientStatus.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)

    def test_opted_in_marketing_campaign_sends_email_and_in_app_notification(self):
        NotificationPreference.objects.create(user=self.attendee, marketing_notifications=True)
        self._order()
        segment = AudienceSegment.objects.create(organization=self.organization, name="Newsletter opt-in", audience_kind=AudienceKind.ALL, marketing_consent_only=True, created_by=self.marketing)
        campaign = create_campaign(organization=self.organization, actor=self.marketing, segment=segment, name="Annonce", kind=CommunicationKind.MARKETING, subject="Nouveauté", body="Un nouvel événement est disponible.", cta_label="Découvrir", cta_url="https://example.com/event")
        launch_campaign(campaign=campaign, actor=self.marketing)
        result = process_due_campaigns()
        campaign.refresh_from_db()
        recipient = CampaignRecipient.objects.get(campaign=campaign)
        self.assertEqual(recipient.status, CampaignRecipientStatus.SENT)
        self.assertEqual(campaign.status, CommunicationCampaignStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.attendee, metadata__campaign_id=str(campaign.pk)).exists())
        self.assertEqual(result["recipients"]["sent"], 1)

    def test_unsubscribe_token_revokes_marketing_consent_and_account_preference(self):
        preference = NotificationPreference.objects.create(user=self.attendee, marketing_notifications=True)
        self._order()
        contact = CRMContact.objects.get(organization=self.organization, email=self.attendee.email)
        segment = AudienceSegment.objects.create(organization=self.organization, name="Unsub", audience_kind=AudienceKind.ALL, created_by=self.marketing)
        campaign = CommunicationCampaign.objects.create(organization=self.organization, segment=segment, name="Unsub campaign", kind=CommunicationKind.MARKETING, subject="Test", body="Test", created_by=self.marketing)
        recipient = CampaignRecipient.objects.create(campaign=campaign, contact=contact, user=self.attendee, email=contact.email)
        unsubscribe_from_token(campaign_unsubscribe_token(recipient))
        contact.refresh_from_db()
        preference.refresh_from_db()
        self.assertEqual(contact.marketing_consent, MarketingConsent.UNSUBSCRIBED)
        self.assertFalse(preference.marketing_notifications)

    def test_event_update_can_reach_guest_ticket_holder_without_marketing_opt_in(self):
        self._ticket(guest=True, email="guest-event@example.com", status=TicketStatus.VALID)
        segment = AudienceSegment.objects.create(organization=self.organization, event=self.event, name="Détenteurs", audience_kind=AudienceKind.TICKET_HOLDERS, created_by=self.marketing)
        campaign = create_campaign(organization=self.organization, actor=self.marketing, segment=segment, event=self.event, name="Changement de salle", kind=CommunicationKind.EVENT_UPDATE, subject="Salle mise à jour", body="Votre événement change de salle.")
        launch_campaign(campaign=campaign, actor=self.marketing)
        process_due_campaigns()
        recipient = CampaignRecipient.objects.get(campaign=campaign, email="guest-event@example.com")
        self.assertEqual(recipient.status, CampaignRecipientStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_scheduled_campaign_is_launched_by_autopilot_processor(self):
        NotificationPreference.objects.create(user=self.attendee, marketing_notifications=True)
        self._order()
        segment = AudienceSegment.objects.create(organization=self.organization, name="Planifié", audience_kind=AudienceKind.ALL, marketing_consent_only=True, created_by=self.marketing)
        campaign = create_campaign(organization=self.organization, actor=self.marketing, segment=segment, name="Planifiée", kind=CommunicationKind.MARKETING, subject="Plus tard", body="Message planifié")
        schedule_campaign(campaign=campaign, actor=self.marketing, scheduled_at=timezone.now() + timedelta(hours=1))
        CommunicationCampaign.objects.filter(pk=campaign.pk).update(scheduled_at=timezone.now() - timedelta(minutes=1))
        result = process_due_campaigns()
        campaign.refresh_from_db()
        self.assertEqual(result["launched"], 1)
        self.assertEqual(campaign.status, CommunicationCampaignStatus.SENT)

    def test_event_manager_can_read_web_crm_but_finance_cannot(self):
        self.client.force_login(self.event_manager)
        self.assertEqual(self.client.get(reverse("crm:organization", kwargs={"slug": self.organization.slug})).status_code, 200)
        self.client.force_login(self.finance)
        self.assertEqual(self.client.get(reverse("crm:organization", kwargs={"slug": self.organization.slug})).status_code, 403)

    def test_api_marketing_can_create_segment_and_finance_is_forbidden(self):
        payload = {"organization_id": str(self.organization.pk), "name": "API buyers", "event_id": str(self.event.pk), "audience_kind": AudienceKind.CONFIRMED_BUYERS, "marketing_consent_only": False}
        self.client.force_login(self.marketing)
        self.assertEqual(self.client.post(reverse("crm_api:segments"), payload, content_type="application/json").status_code, 201)
        self.client.force_login(self.finance)
        payload["name"] = "Finance denied"
        self.assertEqual(self.client.post(reverse("crm_api:segments"), payload, content_type="application/json").status_code, 403)

    def test_contact_visibility_is_isolated_by_organization(self):
        other_org = Organization.objects.create(name="Other CRM Org", created_by=self.owner)
        other_contact = CRMContact.objects.create(organization=other_org, email="private-other@example.com", name="Private")
        self._order()
        self.client.force_login(self.marketing)
        response = self.client.get(reverse("crm_api:contacts"))
        self.assertEqual(response.status_code, 200)
        emails = {row["email"] for row in response.json()}
        self.assertIn(self.attendee.email, emails)
        self.assertNotIn(other_contact.email, emails)

    def test_manual_subscription_requires_documented_source(self):
        self._order()
        contact = CRMContact.objects.get(organization=self.organization, email=self.attendee.email)
        with self.assertRaises(ValidationError):
            set_marketing_consent(contact=contact, actor=self.marketing, subscribed=True, source="")
        contact = set_marketing_consent(contact=contact, actor=self.marketing, subscribed=True, source="newsletter-form")
        self.assertEqual(contact.marketing_consent, MarketingConsent.SUBSCRIBED)
