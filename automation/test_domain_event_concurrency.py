import threading
import unittest

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from activities.models import Activity
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event, process_domain_events
from notifications.models import Notification
from organizations.models import Organization

from .models import AutomationExecution, AutomationRule, DomainAutomationExecutionStatus


User = get_user_model()


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL locking test")
class AutomationDomainEventConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_processors_create_one_execution_and_notification(self):
        owner = User.objects.create_user(username="auto-pg-owner", email="auto-pg-owner@example.com")
        beneficiary = User.objects.create_user(username="auto-pg-beneficiary", email="auto-pg-beneficiary@example.com")
        space = Organization.objects.create(created_by=owner, name="Automation PG Space", slug="automation-pg-space")
        activity = Activity.objects.create(space=space, created_by=owner, title="Automation PG Activity")
        rule = AutomationRule.objects.create(
            space=space,
            activity=activity,
            name="Concurrent notification",
            trigger_event_type=DomainEventType.JOURNEY_SUBMITTED,
            conditions={"workflow": "registration"},
            action_config={
                "recipient": "beneficiary",
                "title": "Concurrent",
                "message": "Une seule notification.",
                "category": "system",
                "queue_email": False,
            },
            created_by=owner,
        )
        event = emit_domain_event(
            event_type=DomainEventType.JOURNEY_SUBMITTED,
            source_type="journey",
            source_id="pg-concurrent",
            idempotency_key="automation:pg:concurrent",
            space_id=space.pk,
            activity_id=activity.pk,
            payload={
                "journey_id": "00000000-0000-0000-0000-000000000001",
                "activity_id": str(activity.pk),
                "beneficiary_id": str(beneficiary.pk),
                "workflow": "registration",
                "status": "submitted",
            },
            process_on_commit=False,
        )
        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            connections["default"].close()
            barrier.wait(timeout=10)
            outcomes.append(process_domain_events(batch_size=1, limit=1))
            connections["default"].close()

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sum(item["claimed"] for item in outcomes), 1)
        self.assertEqual(AutomationExecution.objects.filter(rule=rule, domain_event=event).count(), 1)
        self.assertEqual(
            AutomationExecution.objects.get(rule=rule, domain_event=event).status,
            DomainAutomationExecutionStatus.COMPLETED,
        )
        self.assertEqual(Notification.objects.filter(template_key="automation.rule").count(), 1)
