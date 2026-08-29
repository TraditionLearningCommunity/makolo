from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_services import complete_step, create_step, mark_ready, start_step
from notifications.models import Notification
from organizations.models import Organization
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey

from .service_reminders import run_service_reminders


User = get_user_model()


class T34BReminderTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.owner = User.objects.create_user(username="t34b-rem-owner", email="t34b-rem-owner@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34b-rem-beneficiary", email="t34b-rem-beneficiary@example.com", password="x")
        self.manager = User.objects.create_user(username="t34b-rem-manager", email="t34b-rem-manager@example.com", password="x")
        self.space = Organization.objects.create(name="T34B reminder space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="T34B reminders")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)

    def ready_step(self, *, title, due_at):
        step = create_step(journey=self.journey, title=title, due_at=due_at, created_by=self.manager)
        return mark_ready(step=step, actor=self.manager)

    def test_step_milestone_is_once_per_target_datetime_and_recipient(self):
        step = self.ready_step(title="J-3 task", due_at=self.now + timedelta(days=3))
        run_service_reminders(now=self.now)
        run_service_reminders(now=self.now + timedelta(minutes=15))
        rows = Notification.objects.filter(template_key="service.reminder.step", recipient=self.beneficiary)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().metadata["target_id"], str(step.pk))

    def test_due_date_change_can_create_new_milestone_key(self):
        step = self.ready_step(title="Rescheduled task", due_at=self.now + timedelta(days=3))
        run_service_reminders(now=self.now)
        type(step).objects.filter(pk=step.pk).update(due_at=self.now + timedelta(days=7))
        run_service_reminders(now=self.now)
        rows = Notification.objects.filter(template_key="service.reminder.step", recipient=self.beneficiary)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(len({row.dedup_key for row in rows}), 2)

    def test_completed_step_stops_future_reminders(self):
        step = self.ready_step(title="Completable task", due_at=self.now + timedelta(days=3))
        run_service_reminders(now=self.now)
        step = start_step(step=step, actor=self.manager)
        complete_step(step=step, actor=self.manager)
        run_service_reminders(now=self.now + timedelta(days=2))
        self.assertEqual(
            Notification.objects.filter(template_key="service.reminder.step", recipient=self.beneficiary).count(),
            1,
        )

    def test_overdue_is_not_repeated_every_cycle(self):
        self.ready_step(title="Overdue task", due_at=self.now - timedelta(hours=2))
        run_service_reminders(now=self.now)
        run_service_reminders(now=self.now + timedelta(hours=1))
        rows = Notification.objects.filter(template_key="service.reminder.step", recipient=self.beneficiary)
        self.assertEqual(rows.count(), 1)
        self.assertIn(":overdue:", rows.get().dedup_key)
