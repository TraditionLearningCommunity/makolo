from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.services import issue_access
from activities.models import Activity, Occurrence
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.services import confirm_order, create_order
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType
from domain_events.services import process_domain_events
from journeys.models import WorkflowKind
from journeys.services import confirm_journey, create_journey, submit_journey
from organizations.models import Organization

from .canonical_models import CRMInteraction
from .domain_event_consumer import consume_crm_event
from .models import CRMContact, MarketingConsent


User = get_user_model()


class CanonicalCRMTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="crm-canonical-owner",
            email="owner@canonical-crm.test",
            password="CRM-2026!",
        )
        self.profile = User.objects.create_user(
            username="crm-canonical-profile",
            email="profile@canonical-crm.test",
            first_name="Aline",
            password="CRM-2026!",
        )
        self.space = Organization.objects.create(name="Canonical CRM Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Atelier gratuit")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
        )

    def journey(self, workflow=WorkflowKind.REGISTRATION):
        return create_journey(
            initiated_by=self.profile,
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
        )

    def test_multiple_journeys_create_one_space_profile_contact(self):
        first = self.journey()
        second = self.journey()
        submit_journey(journey=first, actor=self.profile)
        submit_journey(journey=second, actor=self.profile)

        process_domain_events(limit=20)

        self.assertEqual(CRMContact.objects.filter(organization=self.space, user=self.profile).count(), 1)
        contact = CRMContact.objects.get(organization=self.space, user=self.profile)
        self.assertEqual(
            CRMInteraction.objects.filter(
                contact=contact,
                interaction_type=DomainEventType.JOURNEY_SUBMITTED,
            ).count(),
            2,
        )
        self.assertEqual(contact.marketing_consent, MarketingConsent.UNKNOWN)

    def test_free_journey_confirmation_is_crm_fact_without_ticket_or_payment(self):
        journey = self.journey()
        submit_journey(journey=journey, actor=self.profile)
        confirm_journey(journey=journey)

        process_domain_events(limit=20)

        contact = CRMContact.objects.get(organization=self.space, user=self.profile)
        self.assertTrue(
            contact.interactions.filter(interaction_type=DomainEventType.JOURNEY_CONFIRMED).exists()
        )
        self.assertEqual(journey.commerce_orders.count(), 0)

    def test_access_without_ticket_or_journey_is_crm_fact(self):
        access = issue_access(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=None,
            journey=None,
            valid_from=None,
            valid_until=None,
        )
        process_domain_events(limit=20)

        contact = CRMContact.objects.get(organization=self.space, user=self.profile)
        self.assertTrue(
            contact.interactions.filter(
                interaction_type=DomainEventType.ACCESS_ISSUED,
                activity=self.activity,
            ).exists()
        )
        self.assertIsNone(access.journey_id)

    def test_commerce_interaction_uses_payee_space(self):
        payee = Organization.objects.create(name="Commerce Principal", created_by=self.owner)
        journey = self.journey(workflow=WorkflowKind.PURCHASE)
        offer = Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Réservation",
            unit_price=Decimal("20.00"),
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )
        order = create_order(
            journey=journey,
            buyer=self.profile,
            selections=[(offer, 1)],
            payee_space=payee,
        )
        confirm_order(order=order)
        process_domain_events(limit=40)

        payee_contact = CRMContact.objects.get(organization=payee, user=self.profile)
        self.assertTrue(
            payee_contact.interactions.filter(
                interaction_type=DomainEventType.COMMERCE_ORDER_CONFIRMED
            ).exists()
        )

    def test_consumer_redelivery_is_idempotent_and_links_historical_contact(self):
        legacy = CRMContact.objects.create(
            organization=self.space,
            user=None,
            email=self.profile.email,
            name="Historique",
            source="ticket_order",
            marketing_consent=MarketingConsent.SUBSCRIBED,
        )
        journey = self.journey()
        submit_journey(journey=journey, actor=self.profile)
        event = DomainEventOutbox.objects.get(
            source_id=str(journey.pk),
            event_type=DomainEventType.JOURNEY_SUBMITTED,
        )

        consume_crm_event(event)
        consume_crm_event(event)

        legacy.refresh_from_db()
        self.assertEqual(legacy.user_id, self.profile.pk)
        self.assertEqual(legacy.marketing_consent, MarketingConsent.SUBSCRIBED)
        self.assertEqual(
            CRMInteraction.objects.filter(
                contact=legacy,
                domain_event=event,
                interaction_type=DomainEventType.JOURNEY_SUBMITTED,
            ).count(),
            1,
        )
