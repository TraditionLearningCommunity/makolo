from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization
from scanner.models import ScannerAssignment

from .incident_services import create_incident, update_incident
from .models import IncidentCategory, IncidentSeverity, IncidentStatus


User = get_user_model()


class CanonicalOperationsScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("ops-owner-c", "ops-owner-c@example.com", "Ops-2026!")
        self.manager = User.objects.create_user("ops-manager-c", "ops-manager-c@example.com", "Ops-2026!")
        self.scanner = User.objects.create_user("ops-scanner-c", "ops-scanner-c@example.com", "Ops-2026!")
        self.marketing = User.objects.create_user("ops-marketing-c", "ops-marketing-c@example.com", "Ops-2026!")
        self.finance = User.objects.create_user("ops-finance-c", "ops-finance-c@example.com", "Ops-2026!")
        self.space = Organization.objects.create(name="Operations canonical space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Activity A")
        self.other_activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Activity B")
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=2),
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="test",
        )
        grant_space_role(profile=self.marketing, space=self.space, role=SystemRoleCode.MARKETING, granted_by=self.owner)
        grant_space_role(profile=self.finance, space=self.space, role=SystemRoleCode.FINANCE, granted_by=self.owner)

    def test_incident_can_target_activity_occurrence_without_event(self):
        incident = create_incident(
            actor=self.manager,
            title="Incident départ",
            category=IncidentCategory.OTHER,
            severity=IncidentSeverity.MEDIUM,
            activity=self.activity,
            occurrence=self.occurrence,
            description="Incident purement canonique.",
        )
        self.assertIsNone(incident.event_id)
        self.assertEqual(incident.activity_id, self.activity.pk)
        self.assertEqual(incident.occurrence_id, self.occurrence.pk)
        self.assertEqual(incident.organization_id, self.space.pk)

        incident = update_incident(
            incident=incident,
            actor=self.manager,
            status=IncidentStatus.INVESTIGATING,
        )
        self.assertEqual(incident.status, IncidentStatus.INVESTIGATING)

    def test_activity_manager_is_isolated_from_other_activity(self):
        other = create_incident(
            actor=self.owner,
            title="Other activity incident",
            category=IncidentCategory.OTHER,
            severity=IncidentSeverity.LOW,
            activity=self.other_activity,
            description="Other.",
        )
        with self.assertRaises(PermissionDenied):
            update_incident(incident=other, actor=self.manager, status=IncidentStatus.INVESTIGATING)

    def test_scanner_marketing_and_finance_are_not_operations_managers(self):
        ScannerAssignment.objects.create(activity=self.activity, agent=self.scanner)
        for actor in (self.scanner, self.marketing, self.finance):
            with self.assertRaises(PermissionDenied):
                create_incident(
                    actor=actor,
                    title=f"Denied {actor.username}",
                    category=IncidentCategory.OTHER,
                    severity=IncidentSeverity.LOW,
                    activity=self.activity,
                    description="Denied.",
                )

    def test_event_incident_keeps_legacy_projection_and_derives_canonical_scope(self):
        start = timezone.now() + timedelta(days=1)
        event = Event.objects.create(
            organizer=self.owner,
            organization=self.space,
            title="Legacy operations event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
        )
        # Event signals from the previous tasks create its canonical Activity/Occurrence.
        event.refresh_from_db()
        incident = create_incident(
            actor=self.owner,
            title="Legacy bridge incident",
            category=IncidentCategory.EVENT,
            severity=IncidentSeverity.MEDIUM,
            event=event,
            description="Legacy Event projection.",
        )
        self.assertEqual(incident.event_id, event.pk)
        self.assertEqual(incident.activity_id, event.activity_id)
        self.assertEqual(incident.organization_id, self.space.pk)
