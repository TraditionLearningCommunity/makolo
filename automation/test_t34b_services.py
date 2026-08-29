from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey
from notifications.models import Notification
from organizations.models import Organization
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey

from .domain_event_consumer import consume_automation_event
from .models import AutomationExecution, AutomationRule, DomainAutomationExecutionStatus


User = get_user_model()


class T34BAutomationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="t34b-auto-owner", email="t34b-auto-owner@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34b-auto-beneficiary", email="t34b-auto-beneficiary@example.com", password="x")
        self.manager = User.objects.create_user(username="t34b-auto-manager", email="t34b-auto-manager@example.com", password="x")
        self.facilitator = User.objects.create_user(username="t34b-auto-facilitator", email="t34b-auto-facilitator@example.com", password="x")
        self.space = Organization.objects.create(name="T34B automation space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="T34B automation")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.facilitator_mandate = grant_activity_role(
            profile=self.facilitator,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        self.assignment = assign_journey(
            journey=self.journey,
            profile=self.facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )

    def event(self, *, severity="critical", suffix="1"):
        return DomainEventOutbox.objects.create(
            event_type=DomainEventType.JOURNEY_BLOCKER_CREATED,
            source_type="journey_blocker",
            source_id=suffix,
            space_id=self.space.pk,
            activity_id=self.activity.pk,
            payload={
                "journey_id": str(self.journey.pk),
                "beneficiary_id": str(self.beneficiary.pk),
                "severity": severity,
                "status": "active",
            },
            idempotency_key=f"t34b-auto:{suffix}",
        )

    def rule(self, *, recipient="beneficiary", name="Critical blockers"):
        return AutomationRule.objects.create(
            space=self.space,
            activity=self.activity,
            name=name,
            trigger_event_type=DomainEventType.JOURNEY_BLOCKER_CREATED,
            conditions={"severity": "critical"},
            action_config={
                "recipient": recipient,
                "title": "Critical blocker",
                "message": "A controlled Services alert.",
                "category": "service",
                "queue_email": False,
            },
            created_by=self.manager,
        )

    def test_whitelisted_condition_matches_skips_and_retry_is_idempotent(self):
        rule = self.rule()
        matching = self.event(severity="critical", suffix="match")
        consume_automation_event(matching)
        consume_automation_event(matching)
        self.assertEqual(Notification.objects.filter(domain_event=matching, recipient=self.beneficiary).count(), 1)
        execution = AutomationExecution.objects.get(rule=rule, domain_event=matching)
        self.assertEqual(execution.status, DomainAutomationExecutionStatus.COMPLETED)
        self.assertEqual(execution.attempts, 1)

        non_matching = self.event(severity="medium", suffix="skip")
        consume_automation_event(non_matching)
        skipped = AutomationExecution.objects.get(rule=rule, domain_event=non_matching)
        self.assertEqual(skipped.status, DomainAutomationExecutionStatus.SKIPPED)
        self.assertFalse(Notification.objects.filter(domain_event=non_matching).exists())

    def test_assigned_profiles_requires_active_assignment_and_current_authority(self):
        self.rule(recipient="assigned_profiles", name="Assigned critical blockers")
        first = self.event(suffix="assigned-ok")
        consume_automation_event(first)
        self.assertEqual(Notification.objects.filter(domain_event=first, recipient=self.facilitator).count(), 1)

        revoke_mandate(mandate=self.facilitator_mandate)
        second = self.event(suffix="assigned-revoked")
        consume_automation_event(second)
        self.assertFalse(Notification.objects.filter(domain_event=second, recipient=self.facilitator).exists())

    def test_legacy_beneficiary_recipient_remains_compatible(self):
        self.rule(recipient="beneficiary", name="Legacy beneficiary")
        event = self.event(suffix="legacy")
        consume_automation_event(event)
        self.assertTrue(Notification.objects.filter(domain_event=event, recipient=self.beneficiary).exists())
