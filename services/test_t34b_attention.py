from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from core.participant_selectors import participant_actionable_journeys
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_step, mark_ready
from journeys.models import Journey, JourneyStatus
from notifications.models import Notification, NotificationCategory, NotificationKind
from organizations.models import Organization

from .attention_selectors import facilitator_attention_journeys, manager_attention_journeys, participant_service_attention_journeys
from .models import ServiceCurrentOutcome, ServiceJourneyContext, ServiceKind
from .services import create_service_details, create_service_journey


User = get_user_model()


class T34BAttentionTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.owner = User.objects.create_user(username="t34b-att-owner", email="t34b-att-owner@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34b-att-beneficiary", email="t34b-att-beneficiary@example.com", password="x")
        self.manager = User.objects.create_user(username="t34b-att-manager", email="t34b-att-manager@example.com", password="x")
        self.facilitator = User.objects.create_user(username="t34b-att-facilitator", email="t34b-att-facilitator@example.com", password="x")
        self.space = Organization.objects.create(name="T34B attention space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="T34B attention")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        grant_activity_role(profile=self.facilitator, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)

    def case(self, *, beneficiary=None):
        beneficiary = beneficiary or self.beneficiary
        return create_service_journey(service=self.service, initiated_by=beneficiary, beneficiary=beneficiary)

    def test_ready_step_is_participant_attention_and_me_does_not_mark_notifications_read(self):
        journey = self.case()
        step = create_step(journey=journey, title="Participant action", created_by=self.manager)
        mark_ready(step=step, actor=self.manager)
        notification = Notification.objects.create(
            recipient=self.beneficiary,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SERVICE,
            title="Unread",
            message="Must remain unread",
        )
        self.assertTrue(participant_service_attention_journeys(self.beneficiary).filter(pk=journey.pk).exists())
        self.assertTrue(participant_actionable_journeys(self.beneficiary).filter(pk=journey.pk).exists())
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_fulfilled_without_action_is_absent_but_external_action_required_is_separate_attention(self):
        quiet = self.case()
        Journey.objects.filter(pk=quiet.pk).update(status=JourneyStatus.FULFILLED)
        self.assertFalse(participant_service_attention_journeys(self.beneficiary).filter(pk=quiet.pk).exists())

        external = self.case()
        Journey.objects.filter(pk=external.pk).update(status=JourneyStatus.FULFILLED)
        ServiceJourneyContext.objects.filter(pk=external.service_context.pk).update(current_outcome=ServiceCurrentOutcome.ACTION_REQUIRED)
        self.assertTrue(participant_service_attention_journeys(self.beneficiary).filter(pk=external.pk).exists())
        external.refresh_from_db()
        self.assertEqual(external.status, JourneyStatus.FULFILLED)

    def test_facilitator_sees_only_assigned_overdue_case(self):
        assigned = self.case()
        other = self.case()
        assign_journey(
            journey=assigned,
            profile=self.facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )
        create_step(
            journey=assigned,
            title="Overdue assigned",
            due_at=self.now - timedelta(days=1),
            created_by=self.manager,
        )
        create_step(
            journey=other,
            title="Overdue unassigned",
            due_at=self.now - timedelta(days=1),
            created_by=self.manager,
        )
        visible = facilitator_attention_journeys(self.facilitator, now=self.now)
        self.assertTrue(visible.filter(pk=assigned.pk).exists())
        self.assertFalse(visible.filter(pk=other.pk).exists())

    def test_manager_view_all_projects_unassigned_case_without_loading_restricted_documents(self):
        journey = self.case()
        visible = manager_attention_journeys(self.manager, now=self.now)
        self.assertTrue(visible.filter(pk=journey.pk).exists())
        self.assertNotIn("artifacts", {lookup.prefetch_to for lookup in getattr(visible, "_prefetch_related_lookups", ()) if hasattr(lookup, "prefetch_to")})
