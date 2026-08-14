from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity
from domain_events.contracts import DomainEventType
from domain_events.services import process_domain_events
from journeys.models import WorkflowKind
from journeys.services import create_journey, submit_journey
from notifications.models import Notification
from organizations.models import Organization

from .models import AutomationExecution, AutomationRule, DomainAutomationExecutionStatus


User = get_user_model()


class DomainAutomationRuleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="automation-owner",
            email="automation-owner@example.com",
            password="Automation-2026!",
        )
        self.beneficiary = User.objects.create_user(
            username="automation-beneficiary",
            email="automation-beneficiary@example.com",
            password="Automation-2026!",
        )
        self.space = Organization.objects.create(
            created_by=self.owner,
            name="Automation Space",
            slug="automation-domain-space",
        )
        self.other_space = Organization.objects.create(
            created_by=self.owner,
            name="Other Automation Space",
            slug="automation-other-space",
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Automation Activity",
        )
        self.other_activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Other Automation Activity",
        )

    def _rule(self, name="Good rule", **overrides):
        values = {
            "space": self.space,
            "activity": self.activity,
            "name": name,
            "trigger_event_type": DomainEventType.JOURNEY_SUBMITTED,
            "conditions": {"workflow": WorkflowKind.REGISTRATION},
            "action_config": {
                "recipient": "beneficiary",
                "title": "Automation déclenchée",
                "message": "Votre démarche a déclenché une règle contrôlée.",
                "category": "system",
                "queue_email": False,
            },
            "created_by": self.owner,
        }
        values.update(overrides)
        return AutomationRule.objects.create(**values)

    def _journey(self):
        return create_journey(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
        )

    def test_matching_rule_runs_once_and_creates_notification(self):
        rule = self._rule()
        journey = self._journey()
        with self.captureOnCommitCallbacks(execute=True):
            submit_journey(journey=journey, actor=self.beneficiary)

        execution = AutomationExecution.objects.get(rule=rule)
        self.assertEqual(execution.status, DomainAutomationExecutionStatus.COMPLETED)
        self.assertEqual(execution.attempts, 1)
        self.assertEqual(Notification.objects.filter(template_key="automation.rule").count(), 1)

        process_domain_events(limit=10)
        execution.refresh_from_db()
        self.assertEqual(execution.attempts, 1)
        self.assertEqual(Notification.objects.filter(template_key="automation.rule").count(), 1)

    def test_wrong_event_space_activity_inactive_and_conditions_do_not_fire(self):
        right = self._rule(name="Right")
        self._rule(name="Wrong type", trigger_event_type=DomainEventType.JOURNEY_CONFIRMED)
        self._rule(name="Wrong activity", activity=self.other_activity)
        self._rule(name="Inactive", is_active=False)
        self._rule(name="Wrong condition", conditions={"workflow": WorkflowKind.INVITATION})
        AutomationRule.objects.create(
            space=self.other_space,
            name="Wrong space",
            trigger_event_type=DomainEventType.JOURNEY_SUBMITTED,
            action_config={
                "recipient": "beneficiary",
                "title": "Wrong",
                "message": "Wrong",
                "category": "system",
                "queue_email": False,
            },
            created_by=self.owner,
        )
        journey = self._journey()
        with self.captureOnCommitCallbacks(execute=True):
            submit_journey(journey=journey, actor=self.beneficiary)

        completed = AutomationExecution.objects.filter(
            status=DomainAutomationExecutionStatus.COMPLETED
        )
        self.assertEqual(completed.count(), 1)
        self.assertEqual(completed.get().rule_id, right.pk)
        self.assertTrue(
            AutomationExecution.objects.filter(
                rule__name="Wrong condition",
                status=DomainAutomationExecutionStatus.SKIPPED,
            ).exists()
        )
        self.assertFalse(AutomationExecution.objects.filter(rule__name="Wrong type").exists())
        self.assertFalse(AutomationExecution.objects.filter(rule__name="Wrong activity").exists())
        self.assertFalse(AutomationExecution.objects.filter(rule__name="Wrong space").exists())
        self.assertFalse(AutomationExecution.objects.filter(rule__name="Inactive").exists())

    def test_failed_rule_retries_to_limit_without_duplicate_effect(self):
        rule = self._rule(
            name="Missing buyer",
            action_config={
                "recipient": "buyer",
                "title": "Impossible",
                "message": "Ce trigger ne fournit pas buyer_id.",
                "category": "system",
                "queue_email": False,
            },
        )
        journey = self._journey()
        with self.captureOnCommitCallbacks(execute=True):
            submit_journey(journey=journey, actor=self.beneficiary)

        process_domain_events(limit=1)
        process_domain_events(limit=1)
        process_domain_events(limit=1)
        execution = AutomationExecution.objects.get(rule=rule)
        self.assertEqual(execution.status, DomainAutomationExecutionStatus.FAILED)
        self.assertEqual(execution.attempts, 3)
        self.assertEqual(Notification.objects.filter(template_key="automation.rule").count(), 0)
