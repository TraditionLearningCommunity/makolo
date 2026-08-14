from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.services import issue_access
from accounts.models import NotificationPreference
from activities.models import Activity, Occurrence
from activities.services import cancel_occurrence, reschedule_occurrence
from commerce.models import OfferStatus, PaymentMode
from commerce.services import confirm_order, create_offer, create_order
from journeys.models import WorkflowKind
from journeys.services import (
    approve_request,
    confirm_journey,
    create_journey,
    create_request,
    require_payment,
    submit_journey,
)
from organizations.models import Organization
from payments.models import Payment
from tickets.models import Ticket, TicketOrder

from .models import DeliveryStatus, Notification, NotificationKind


User = get_user_model()


class DomainEventNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="domain-notify-owner",
            email="domain-notify-owner@example.com",
            password="Domain-notify-2026!",
        )
        self.beneficiary = User.objects.create_user(
            username="domain-notify-beneficiary",
            email="domain-notify-beneficiary@example.com",
            password="Domain-notify-2026!",
        )
        self.unrelated = User.objects.create_user(
            username="domain-notify-unrelated",
            email="domain-notify-unrelated@example.com",
            password="Domain-notify-2026!",
        )
        self.space = Organization.objects.create(
            created_by=self.owner,
            name="Domain Notifications Space",
            slug="domain-notifications-space",
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Atelier Makolo générique",
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
            timezone="Europe/Brussels",
        )

    def _journey(self, workflow=WorkflowKind.REGISTRATION):
        return create_journey(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
        )

    def test_free_registration_notifies_without_ticket_or_payment_and_is_deduplicated(self):
        journey = self._journey()
        with self.captureOnCommitCallbacks(execute=True):
            submit_journey(journey=journey, actor=self.beneficiary)
            confirm_journey(journey=journey)
            issue_access(
                beneficiary=self.beneficiary,
                activity=self.activity,
                occurrence=self.occurrence,
                journey=journey,
                source_key="registration",
            )

        notifications = Notification.objects.filter(recipient=self.beneficiary)
        self.assertEqual(notifications.count(), 1)
        notification = notifications.get()
        self.assertIn("Inscription confirmée", notification.title)
        self.assertNotIn("billet", notification.message.lower())
        self.assertIsNotNone(notification.domain_event_id)
        self.assertEqual(notification.journey_id, journey.pk)
        self.assertEqual(TicketOrder.objects.count(), 0)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_after_approval_emits_payment_required_notification_without_event_or_ticket(self):
        journey = self._journey(WorkflowKind.ORDER_APPROVAL)
        submit_journey(journey=journey, actor=self.beneficiary)
        request = create_request(journey=journey, requester=self.beneficiary)

        with self.captureOnCommitCallbacks(execute=True):
            approve_request(request=request, actor=self.owner, comment="OK")
            require_payment(journey=journey, reason="approved_then_payment")

        titles = list(
            Notification.objects.filter(recipient=self.beneficiary).values_list("title", flat=True)
        )
        self.assertIn("Demande approuvée", titles)
        self.assertIn("Paiement requis", titles)
        self.assertEqual(TicketOrder.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_on_site_order_confirms_without_payment_received_wording(self):
        journey = self._journey(WorkflowKind.RESERVATION)
        submit_journey(journey=journey, actor=self.beneficiary)
        offer = create_offer(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Réservation sur place",
            unit_price=Decimal("20.00"),
            currency="EUR",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )
        order = create_order(
            journey=journey,
            buyer=self.beneficiary,
            selections=[{"offer": offer, "quantity": 1}],
            payee_space=self.space,
        )

        with self.captureOnCommitCallbacks(execute=True):
            confirm_order(order=order)

        notification = Notification.objects.get(recipient=self.beneficiary)
        self.assertIn("paiement", notification.message.lower())
        self.assertIn("sur place", notification.message.lower())
        self.assertNotIn("paiement confirmé", notification.title.lower())
        self.assertEqual(Payment.objects.count(), 0)

    def test_occurrence_changes_notify_only_canonical_participants(self):
        journey = self._journey()
        submit_journey(journey=journey, actor=self.beneficiary)
        confirm_journey(journey=journey)
        issue_access(
            beneficiary=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            source_key="occurrence-change",
        )
        new_start = self.occurrence.start_at + timedelta(hours=1)
        new_end = self.occurrence.end_at + timedelta(hours=1)

        with self.captureOnCommitCallbacks(execute=True):
            reschedule_occurrence(
                occurrence=self.occurrence,
                start_at=new_start,
                end_at=new_end,
                timezone="Europe/Brussels",
            )
            cancel_occurrence(occurrence=self.occurrence)

        messages = Notification.objects.filter(recipient=self.beneficiary)
        self.assertTrue(messages.filter(template_key="occurrence.rescheduled").exists())
        self.assertTrue(messages.filter(template_key="occurrence.cancelled").exists())
        self.assertFalse(Notification.objects.filter(recipient=self.unrelated).exists())

    def test_domain_notification_respects_email_opt_out_but_keeps_in_app(self):
        NotificationPreference.objects.update_or_create(
            user=self.beneficiary,
            defaults={"email_notifications": False},
        )
        journey = self._journey()
        with self.captureOnCommitCallbacks(execute=True):
            submit_journey(journey=journey, actor=self.beneficiary)
            confirm_journey(journey=journey)

        notification = Notification.objects.get(recipient=self.beneficiary)
        self.assertEqual(notification.deliveries.get().status, DeliveryStatus.SKIPPED)
        self.assertTrue(Notification.objects.filter(pk=notification.pk, read_at__isnull=True).exists())
