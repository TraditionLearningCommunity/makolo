from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessUse, AccessUseResult
from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .checkpoint_services import observe_checkpoint, open_checkpoint
from .models import CheckpointObservation, OccurrenceCheckpoint


User = get_user_model()


class O2CheckpointAPITests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o2-api-owner", email="o2-api-owner@example.test", password="pw")
        self.operator = User.objects.create_user(username="o2-api-operator", email="o2-api-operator@example.test", password="pw")
        self.participant = User.objects.create_user(username="o2-api-participant", email="o2-api-participant@example.test", password="pw")
        self.other = User.objects.create_user(username="o2-api-other", email="o2-api-other@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 API")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O2 API occurrence",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=2),
        )
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="entry",
            label="Entrée",
            position=1,
        )
        self.other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 API other")
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="O2 API other occurrence",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
        )
        self.other_checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.other_occurrence,
            key="entry",
            label="Other entry",
        )
        grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o2-api-test",
        )
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

    def test_participant_sees_only_own_occurrence_flow(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-checkpoints-me", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["checkpoint"]["label"], "Entrée")
        other_response = self.client.get(reverse("operations_api:occurrence-checkpoints-me", args=[self.other_occurrence.pk]))
        self.assertEqual(other_response.status_code, 404)

    def test_operator_can_read_minimal_observations_without_email(self):
        open_checkpoint(actor=self.operator, checkpoint=self.checkpoint)
        observation = observe_checkpoint(
            actor=self.operator,
            checkpoint=self.checkpoint,
            profile=self.participant,
            source="operator",
            client_reference="api-read",
        )
        self.client.force_login(self.operator)
        response = self.client.get(reverse("operations_api:checkpoint-observations", args=[self.checkpoint.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], str(observation.pk))
        self.assertEqual(response.json()[0]["beneficiary"]["type"], "profile")
        self.assertNotIn(self.participant.email, str(response.json()))

    def test_operator_cannot_read_or_mutate_checkpoint_from_other_activity(self):
        self.client.force_login(self.operator)
        read_response = self.client.get(
            reverse("operations_api:checkpoint-observations", args=[self.other_checkpoint.pk])
        )
        self.assertEqual(read_response.status_code, 404)
        response = self.client.patch(
            reverse("operations_api:checkpoint-status", args=[self.other_checkpoint.pk]),
            {"action": "open"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.other_checkpoint.refresh_from_db()
        self.assertEqual(self.other_checkpoint.status, "planned")

    def test_observation_rejects_access_use_from_other_occurrence(self):
        open_checkpoint(actor=self.operator, checkpoint=self.checkpoint)
        other_access = Access.objects.create(
            beneficiary=self.participant,
            activity=self.other_activity,
            occurrence=self.other_occurrence,
            status="valid",
        )
        other_use = AccessUse.objects.create(
            access=other_access,
            actor=self.operator,
            occurrence=self.other_occurrence,
            result=AccessUseResult.ACCEPTED,
        )
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("operations_api:checkpoint-observations", args=[self.checkpoint.pk]),
            {
                "profile_id": str(self.participant.pk),
                "access_use_id": str(other_use.pk),
                "source": "scanner",
                "client_reference": "cross-occurrence",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CheckpointObservation.objects.filter(checkpoint=self.checkpoint).exists())

    def test_assignment_mutation_outside_authority_is_hidden(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("operations_api:checkpoint-assignments", args=[self.other_checkpoint.pk]),
            {"profile_id": str(self.operator.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
