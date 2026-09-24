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

from automation.scheduler import run_autopilot_cycle as run_scheduler_autopilot_cycle
from automation.services import ensure_policy, run_autopilot_cycle as run_legacy_autopilot_cycle


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

        run_legacy_autopilot_cycle(delivery_limit=10)

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

        run_legacy_autopilot_cycle(delivery_limit=1)

        followup.assert_not_called()


    def test_scheduler_cycle_covers_all_time_driven_owner_work(self):
        with (
            patch(
                "automation.scheduler.is_operational_control_enabled",
                return_value=True,
            ),
            patch(
                "automation.scheduler.expire_stale_capacity_reservations",
                return_value=2,
            ) as expire_capacity,
            patch(
                "automation.scheduler.expire_due_journeys",
                return_value=3,
            ) as expire_journeys,
            patch(
                "automation.scheduler.recover_stale_domain_events",
                return_value=4,
            ) as recover_events,
            patch(
                "automation.scheduler.process_domain_events",
                return_value={"processed": 5},
            ) as process_events,
            patch(
                "automation.scheduler.run_legacy_autopilot_cycle",
                return_value={"deliveries": {"sent": 1}},
            ) as legacy_cycle,
            patch(
                "automation.scheduler.run_service_reminders",
                return_value={"created": 0},
            ),
            patch(
                "automation.scheduler.run_subscription_deadlines",
                return_value={"processed": 0},
            ),
            patch(
                "automation.scheduler.run_spatiotemporal_automation_cycle",
                return_value={"processed": 0},
            ),
            patch(
                "automation.scheduler.run_proactive_preparation_cycle",
                return_value={"processed": 0},
            ),
            patch(
                "automation.scheduler.process_due_conversation_points",
                return_value={"processed": 0},
            ),
            patch(
                "automation.scheduler.run_default_recognition_cycle",
                return_value={"processed": 0},
            ),
            patch(
                "automation.scheduler.expire_captures",
                return_value=6,
            ),
            patch(
                "automation.scheduler.process_due_crm_workflows",
                return_value={"processed": 7},
            ) as crm_workflows,
        ):
            stats = run_scheduler_autopilot_cycle(delivery_limit=11)

        self.assertEqual(stats["expired_capacity_holds"], 2)
        self.assertEqual(stats["expired_journeys"], 3)
        self.assertEqual(stats["recovered_domain_events"], 4)
        self.assertEqual(stats["domain_events"], {"processed": 5})
        self.assertEqual(stats["deliveries"], {"sent": 1})
        self.assertEqual(stats["expired_inbound_captures"], 6)
        self.assertEqual(stats["crm_workflows"], {"processed": 7})
        expire_capacity.assert_called_once_with()
        expire_journeys.assert_called_once_with()
        recover_events.assert_called_once_with()
        process_events.assert_called_once_with(batch_size=11, limit=11)
        legacy_cycle.assert_called_once_with(now=None, delivery_limit=11)
        crm_workflows.assert_called_once_with(limit=11)

    @patch(
        "automation.management.commands.run_autopilot.run_autopilot_cycle",
        return_value={"deliveries": {"sent": 0}},
    )
    def test_scheduled_one_shot_records_non_persistent_heartbeat(self, _cycle):
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
