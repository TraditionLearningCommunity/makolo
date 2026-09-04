from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import OccurrenceQueue, QueueEntry, QueueEntryStatus


User = get_user_model()


class O3QueueAPITests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o3-api-owner", email="o3-api-owner@example.test", password="pw")
        self.operator = User.objects.create_user(username="o3-api-operator", email="o3-api-operator@example.test", password="pw")
        self.participant = User.objects.create_user(username="o3-api-participant", email="o3-api-participant@example.test", password="pw")
        self.other = User.objects.create_user(username="o3-api-other", email="o3-api-other@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O3 API")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O3 API occurrence",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=2),
        )
        grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o3-api-test",
        )
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            key="main",
            label="File principale",
        )
        self.other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O3 API other")
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="Other occurrence",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
        )
        self.other_queue = OccurrenceQueue.objects.create(
            occurrence=self.other_occurrence,
            key="main",
            label="Other queue",
        )

    def test_operator_can_enter_call_and_serve(self):
        self.client.force_login(self.operator)
        entered = self.client.post(
            reverse("operations_api:queue-entries", args=[self.queue.pk]),
            {"profile_id": str(self.participant.pk), "client_reference": "api-enter"},
            content_type="application/json",
        )
        self.assertEqual(entered.status_code, 201)
        entry_id = entered.json()["id"]
        called = self.client.post(reverse("operations_api:queue-call-next", args=[self.queue.pk]))
        self.assertEqual(called.status_code, 200)
        self.assertEqual(called.json()["id"], entry_id)
        served = self.client.post(reverse("operations_api:queue-entry-action", args=[entry_id, "serve"]))
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.json()["status"], QueueEntryStatus.SERVED)

    def test_participant_can_enter_self_and_read_only_own_queue_state(self):
        self.client.force_login(self.participant)
        entered = self.client.post(
            reverse("operations_api:queue-entry-me", args=[self.queue.pk]),
            {"client_reference": "self-enter"},
            content_type="application/json",
        )
        self.assertEqual(entered.status_code, 201)
        mine = self.client.get(reverse("operations_api:occurrence-queues-me", args=[self.occurrence.pk]))
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.json()), 1)
        self.assertEqual(mine.json()[0]["beneficiary"]["id"], str(self.participant.pk))
        forbidden_other_occurrence = self.client.get(
            reverse("operations_api:occurrence-queues-me", args=[self.other_occurrence.pk])
        )
        self.assertEqual(forbidden_other_occurrence.status_code, 404)

    def test_operator_cannot_mutate_queue_from_other_activity(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("operations_api:queue-entries", args=[self.other_queue.pk]),
            {"profile_id": str(self.participant.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(QueueEntry.objects.filter(queue=self.other_queue).exists())

    def test_unprivileged_user_cannot_list_operational_entries(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("operations_api:queue-entries", args=[self.queue.pk]))
        self.assertEqual(response.status_code, 404)

    def test_participant_cannot_cancel_another_participants_entry(self):
        second = User.objects.create_user(username="o3-api-second", email="o3-api-second@example.test", password="pw")
        Journey.objects.create(
            initiated_by=second,
            beneficiary=second,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.client.force_login(second)
        entered = self.client.post(reverse("operations_api:queue-entry-me", args=[self.queue.pk]))
        entry_id = entered.json()["id"]
        self.client.force_login(self.participant)
        response = self.client.post(reverse("operations_api:queue-entry-me-cancel", args=[entry_id]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(QueueEntry.objects.get(pk=entry_id).status, QueueEntryStatus.WAITING)
