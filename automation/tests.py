from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from notifications.models import Notification, NotificationKind
from organizations.services import create_organization
from tickets.models import Ticket, TicketOrderStatus, TicketStatus, TicketType
from tickets.services import create_order

from .models import AutomationRun
from .services import ensure_policy, run_autopilot_cycle


User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AutopilotCycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="auto-owner", email="auto-owner@makolo.test", password="StrongPass2026!")
        self.buyer = User.objects.create_user(username="auto-buyer", email="auto-buyer@makolo.test", password="StrongPass2026!")
        self.organization = create_organization(creator=self.owner, name="Autopilot Events")

    def make_event(self, *, start_delta=timedelta(hours=23), duration=timedelta(hours=3), capacity=20):
        start = timezone.now() + start_delta
        return Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title=f"Autopilot Test {abs(int(start_delta.total_seconds()))}",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + duration,
            capacity=capacity,
            published_at=timezone.now(),
        )

    def issue_free_ticket(self, event):
        ticket_type = TicketType.objects.create(event=event, name="Standard", price=0, currency="USD", quantity_total=20, max_per_order=5)
        order = create_order(
            buyer=self.buyer,
            event=event,
            customer_name="Auto Buyer",
            customer_email=self.buyer.email,
            selections=[(ticket_type, 1)],
        )
        return ticket_type, order, order.tickets.get()

    def test_24h_reminder_is_generated_once(self):
        event = self.make_event(start_delta=timedelta(hours=23, minutes=50))
        self.issue_free_ticket(event)
        policy = ensure_policy(event)
        policy.reminder_7d_enabled = False
        policy.reminder_24h_enabled = True
        policy.reminder_2h_enabled = False
        policy.save()

        run_autopilot_cycle(delivery_limit=10)
        run_autopilot_cycle(delivery_limit=10)

        reminders = Notification.objects.filter(recipient=self.buyer, kind=NotificationKind.EVENT_REMINDER)
        self.assertEqual(reminders.count(), 1)
        self.assertEqual(AutomationRun.objects.filter(rule_key="event-reminder-24h").count(), 1)

    def test_expired_pending_order_is_released_automatically(self):
        event = self.make_event(start_delta=timedelta(days=2))
        ticket_type = TicketType.objects.create(event=event, name="Payant", price=10, currency="USD", quantity_total=5)
        order = create_order(
            buyer=self.buyer,
            event=event,
            customer_name="Auto Buyer",
            customer_email=self.buyer.email,
            selections=[(ticket_type, 1)],
            hold_minutes=1,
        )
        order.expires_at = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=["expires_at", "updated_at"])

        run_autopilot_cycle(delivery_limit=10)
        order.refresh_from_db()
        ticket_type.refresh_from_db()
        self.assertEqual(order.status, TicketOrderStatus.EXPIRED)
        self.assertEqual(ticket_type.reserved_quantity, 0)

    def test_event_is_completed_and_sales_closed_without_human_action(self):
        event = self.make_event(start_delta=timedelta(hours=-3), duration=timedelta(hours=1))
        ticket_type = TicketType.objects.create(event=event, name="Late", price=0, quantity_total=10)
        policy = ensure_policy(event)
        policy.auto_complete_event = True
        policy.auto_close_sales_at_start = True
        policy.post_event_followup_enabled = False
        policy.save()

        run_autopilot_cycle(delivery_limit=10)
        event.refresh_from_db()
        ticket_type.refresh_from_db()
        self.assertEqual(event.status, EventStatus.COMPLETED)
        self.assertFalse(ticket_type.is_active)

    def test_capacity_and_low_stock_alerts_go_to_organization_team(self):
        event = self.make_event(capacity=2)
        ticket_type, order, ticket = self.issue_free_ticket(event)
        ticket_type.quantity_total = 1
        ticket_type.save(update_fields=["quantity_total", "updated_at"])
        policy = ensure_policy(event)
        policy.capacity_alert_percent = 50
        policy.low_stock_threshold = 1
        policy.save()

        run_autopilot_cycle(delivery_limit=10)
        titles = list(Notification.objects.filter(recipient=self.owner).values_list("title", flat=True))
        self.assertTrue(any("capacité" in title for title in titles))
        self.assertTrue(any("Stock faible" in title for title in titles))
