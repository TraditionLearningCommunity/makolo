from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from notifications.models import Notification, NotificationKind
from operations.models import WorkerHeartbeat, WorkerState
from organizations.services import create_organization
from tickets.models import TicketType
from tickets.services import create_order

from automation.services import ensure_policy, run_autopilot_cycle


User = get_user_model()


class AutopilotOperationalHardeningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ops-auto-owner",
            email="ops-auto-owner@example.com",
            password="StrongPass2026!",
        )
        self.buyer = User.objects.create_user(
            username="ops-auto-buyer",
            email="ops-auto-buyer@example.com",
            password="StrongPass2026!",
        )
        self.organization = create_organization(
            creator=self.owner,
            name="Operational Autopilot",
        )

    def _event(self, *, start_delta, status=EventStatus.PUBLISHED):
        start = timezone.now() + start_delta
        published_at = timezone.now() if status == EventStatus.PUBLISHED else None
        return Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title=f"Operational Event {start_delta.total_seconds()}",
            status=status,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=1),
            capacity=50,
            published_at=published_at,
        )

    def _issue_ticket(self, event):
        ticket_type = TicketType.objects.create(
            event=event,
            name="Standard",
            price=0,
            currency="USD",
            quantity_total=50,
        )
        return create_order(
            buyer=self.buyer,
            event=event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(ticket_type, 1)],
        )

    def test_hourly_scheduler_still_catches_two_hour_reminder(self):
        event = self._event(start_delta=timedelta(hours=1, minutes=10))
        self._issue_ticket(event)
        policy = ensure_policy(event)
        policy.reminder_7d_enabled = False
        policy.reminder_24h_enabled = False
        policy.reminder_2h_enabled = True
        policy.save()

        run_autopilot_cycle(delivery_limit=10)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.buyer,
                kind=NotificationKind.EVENT_REMINDER,
            ).count(),
            1,
        )

    @patch("automation.services._post_event_followup")
    def test_completed_events_older_than_catchup_window_are_not_reprocessed(self, followup):
        old_event = self._event(
            start_delta=timedelta(days=-40),
            status=EventStatus.COMPLETED,
        )
        Event.objects.filter(pk=old_event.pk).update(
            end_at=timezone.now() - timedelta(days=31),
        )

        run_autopilot_cycle(delivery_limit=1)

        followup.assert_not_called()

    @patch(
        "automation.management.commands.run_autopilot.process_due_crm_workflows",
        return_value={"processed": 0},
    )
    @patch(
        "automation.management.commands.run_autopilot.run_autopilot_cycle",
        return_value={"deliveries": {"sent": 0}},
    )
    def test_scheduled_one_shot_records_non_persistent_heartbeat(self, _cycle, _crm):
        output = StringIO()
        call_command(
            "run_autopilot",
            delivery_limit=1,
            record_scheduled_heartbeat=True,
            instance_id="scheduled-test",
            stdout=output,
        )

        heartbeat = WorkerHeartbeat.objects.get(
            worker_name="autopilot",
            instance_id="scheduled-test",
        )
        self.assertEqual(heartbeat.state, WorkerState.STOPPED)
        self.assertEqual(heartbeat.metadata["mode"], "scheduled")
        self.assertEqual(heartbeat.metadata["expected_interval_seconds"], 3600)
        self.assertIsNotNone(heartbeat.last_cycle_started_at)
        self.assertIsNotNone(heartbeat.last_cycle_finished_at)
