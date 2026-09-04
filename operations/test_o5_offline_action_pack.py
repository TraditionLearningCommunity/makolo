from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from core.models import DomainEventOutbox
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization

from .models import (
    CheckpointStatus,
    OccurrenceCheckpoint,
    OccurrenceQueue,
    PlacementAssignment,
    PlacementPlan,
    PlacementUnit,
    QueueEntry,
    QueueEntryStatus,
)
from .offline_action_pack import offline_action_pack_freshness


User = get_user_model()


class O5OfflineActionPackTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="o5-owner", email="o5-owner@example.test", password="pw")
        self.operator = User.objects.create_user(username="o5-operator", email="o5-operator@example.test", password="pw")
        self.participant = User.objects.create_user(
            username="o5-participant", email="o5-participant@example.test", password="pw"
        )
        self.other_participant = User.objects.create_user(
            username="o5-other", email="private-other@example.test", password="pw"
        )
        self.stranger = User.objects.create_user(username="o5-stranger", email="o5-stranger@example.test", password="pw")
        self.space = Organization.objects.create(name="O5 Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="O5 Other Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="O5 Offline")
        self.other_activity = Activity.objects.create(space=self.other_space, created_by=self.owner, title="O5 Other")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O5 active occurrence",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="O5 other occurrence",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        Journey.objects.create(
            initiated_by=self.other_participant,
            beneficiary=self.other_participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="boarding",
            label="Boarding",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        self.queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            checkpoint=self.checkpoint,
            key="boarding",
            label="Boarding queue",
        )
        QueueEntry.objects.create(
            queue=self.queue,
            profile=self.participant,
            sequence=1,
            status=QueueEntryStatus.WAITING,
            entered_by=self.participant,
        )
        QueueEntry.objects.create(
            queue=self.queue,
            profile=self.other_participant,
            sequence=2,
            status=QueueEntryStatus.WAITING,
            entered_by=self.other_participant,
        )
        self.plan = PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="vehicle",
            label="Vehicle",
            required=True,
        )
        participant_unit = PlacementUnit.objects.create(
            plan=self.plan,
            key="seat-1",
            label="Seat 1",
            kind="seat",
        )
        other_unit = PlacementUnit.objects.create(
            plan=self.plan,
            key="seat-2",
            label="PRIVATE Seat 2",
            kind="seat",
        )
        self.move_unit = PlacementUnit.objects.create(
            plan=self.plan,
            key="seat-3",
            label="Seat 3",
            kind="seat",
        )
        self.participant_placement = PlacementAssignment.objects.create(
            plan=self.plan,
            unit=participant_unit,
            profile=self.participant,
            assigned_by=self.owner,
        )
        PlacementAssignment.objects.create(
            plan=self.plan,
            unit=other_unit,
            profile=self.other_participant,
            assigned_by=self.owner,
        )
        self.operator_mandate = grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o5-test",
        )

    def _get_pack(self, user, occurrence=None):
        self.client.force_login(user)
        occurrence = occurrence or self.occurrence
        return self.client.get(reverse("operations_api:occurrence-offline-action-pack", args=[occurrence.pk]))

    def _complete_occurrence(self):
        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.end_at = self.now
        self.occurrence.save(update_fields=["status", "end_at", "updated_at"])

    def test_authorized_operator_gets_viewer_aware_pack(self):
        before = DomainEventOutbox.objects.count()
        response = self._get_pack(self.operator)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        payload = response.json()
        self.assertEqual(payload["schema"], "operations.offline_action_pack")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["snapshot"]["perspective"], "operator")
        self.assertEqual(payload["snapshot"]["occurrence"]["id"], str(self.occurrence.pk))
        self.assertEqual(payload["freshness"]["state"], "fresh")
        self.assertFalse(payload["freshness"]["refresh_required"])
        self.assertFalse(payload["execution_contract"]["offline_data_grants_authority"])
        self.assertTrue(payload["execution_contract"]["server_revalidation_required"])
        self.assertEqual(payload["execution_contract"]["revocation_policy"], "server_current_state")
        self.assertIn("operations.occurrence_live", payload["provenance"]["sources"])
        self.assertEqual(DomainEventOutbox.objects.count(), before)

    def test_participant_pack_contains_only_own_operational_view(self):
        response = self._get_pack(self.participant)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["perspective"], "participant")
        self.assertEqual(snapshot["placement"][0]["unit"], "Seat 1")
        self.assertEqual(snapshot["queue"][0]["status"], "waiting")
        rendered = str(payload)
        self.assertNotIn(self.other_participant.email, rendered)
        self.assertNotIn("PRIVATE Seat 2", rendered)
        self.assertNotIn("assignments", snapshot)
        self.assertNotIn("scanner", snapshot)

    def test_user_without_right_is_hidden(self):
        response = self._get_pack(self.stranger)
        self.assertEqual(response.status_code, 404)

    def test_cross_occurrence_idor_is_hidden(self):
        response = self._get_pack(self.participant, self.other_occurrence)
        self.assertEqual(response.status_code, 404)

    def test_freshness_contract_identifies_stale_and_expired_snapshot(self):
        stale = offline_action_pack_freshness(
            occurrence=self.occurrence,
            phase="live",
            generated_at=self.now,
            evaluated_at=self.now + timedelta(minutes=2),
        )
        expired = offline_action_pack_freshness(
            occurrence=self.occurrence,
            phase="live",
            generated_at=self.now,
            evaluated_at=self.now + timedelta(minutes=16),
        )
        self.assertEqual(stale["state"], "stale")
        self.assertTrue(stale["stale"])
        self.assertFalse(stale["expired"])
        self.assertTrue(stale["refresh_required"])
        self.assertEqual(expired["state"], "expired")
        self.assertTrue(expired["stale"])
        self.assertTrue(expired["expired"])
        self.assertTrue(expired["refresh_required"])

    def test_pack_has_no_sensitive_or_transport_only_fields(self):
        response = self._get_pack(self.participant)
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        def keys(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    yield key.lower()
                    yield from keys(item)
            elif isinstance(value, list):
                for item in value:
                    yield from keys(item)

        forbidden_keys = {
            "credential",
            "credentials",
            "email",
            "itinerary_url",
            "payment",
            "payments",
            "phone",
            "phone_number",
            "public_id",
            "qr",
            "qr_code",
            "secret",
            "token",
            "url",
        }
        self.assertTrue(forbidden_keys.isdisjoint(set(keys(payload["snapshot"]))))
        self.assertNotIn(self.other_participant.email, str(payload))
        self.assertNotIn("PRIVATE Seat 2", str(payload))

    def test_server_mutation_revalidates_current_authority_after_pack_download(self):
        response = self._get_pack(self.operator)
        self.assertEqual(response.status_code, 200)

        revoke_mandate(mandate=self.operator_mandate, actor=self.owner)
        self.client.force_login(self.operator)
        mutation = self.client.patch(
            reverse("operations_api:queue-status", args=[self.queue.pk]),
            data={"action": "pause"},
            content_type="application/json",
        )
        self.assertEqual(mutation.status_code, 404)
        self.queue.refresh_from_db()
        self.assertNotEqual(self.queue.status, "paused")

    def test_server_mutations_revalidate_current_occurrence_after_pack_download(self):
        response = self._get_pack(self.operator)
        self.assertEqual(response.status_code, 200)
        self._complete_occurrence()
        self.client.force_login(self.operator)

        queue_response = self.client.patch(
            reverse("operations_api:queue-status", args=[self.queue.pk]),
            data={"action": "pause"},
            content_type="application/json",
        )
        checkpoint_response = self.client.patch(
            reverse("operations_api:checkpoint-status", args=[self.checkpoint.pk]),
            data={"action": "pause"},
            content_type="application/json",
        )
        placement_response = self.client.patch(
            reverse("operations_api:placement-assignment-detail", args=[self.participant_placement.pk]),
            data={"unit_id": str(self.move_unit.pk)},
            content_type="application/json",
        )

        self.assertEqual(queue_response.status_code, 400)
        self.assertEqual(checkpoint_response.status_code, 400)
        self.assertEqual(placement_response.status_code, 400)
        self.queue.refresh_from_db()
        self.checkpoint.refresh_from_db()
        self.participant_placement.refresh_from_db()
        self.assertNotEqual(self.queue.status, "paused")
        self.assertNotEqual(self.checkpoint.status, "paused")
        self.assertIsNone(self.participant_placement.ended_at)

    def test_terminal_cleanup_remains_available_after_occurrence_end(self):
        self._complete_occurrence()
        self.client.force_login(self.operator)
        queue_response = self.client.patch(
            reverse("operations_api:queue-status", args=[self.queue.pk]),
            data={"action": "close"},
            content_type="application/json",
        )
        checkpoint_response = self.client.patch(
            reverse("operations_api:checkpoint-status", args=[self.checkpoint.pk]),
            data={"action": "close"},
            content_type="application/json",
        )
        placement_response = self.client.delete(
            reverse("operations_api:placement-assignment-detail", args=[self.participant_placement.pk])
        )
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(checkpoint_response.status_code, 200)
        self.assertEqual(placement_response.status_code, 204)

    def test_historical_occurrence_without_operations_configuration_is_compatible(self):
        historical = Occurrence.objects.create(
            activity=self.activity,
            label="Historical plain occurrence",
            start_at=self.now - timedelta(hours=3),
            end_at=self.now - timedelta(hours=2),
            status=OccurrenceStatus.COMPLETED,
        )
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=historical,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

        response = self._get_pack(self.participant, historical)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["freshness"]["state"], "expired")
        self.assertEqual(payload["snapshot"]["placement"], [])
        self.assertEqual(payload["snapshot"]["flow"]["checkpoints"], [])
        self.assertEqual(payload["snapshot"]["queue"], [])
