from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import (
    Activity,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from core.models import DomainEventOutbox
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from spatiotemporal.providers import (
    NoOpRoutingProvider,
    NoOpTrafficProvider,
    ProviderRegistry,
    ProviderUnavailable,
    WeatherProvider,
    reset_provider_registry,
    set_provider_registry,
)

from .models import (
    CheckpointAssignment,
    CheckpointStatus,
    OccurrenceCheckpoint,
    OccurrenceQueue,
    PlacementAssignment,
    PlacementPlan,
    PlacementUnit,
    QueueEntry,
    QueueEntryStatus,
)


User = get_user_model()


class UnavailableWeatherProvider(WeatherProvider):
    key = "unavailable-weather"

    def weather_context(self, *, place, at, observed_at):
        raise ProviderUnavailable("weather unavailable")


class O4OccurrenceLiveAPITests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="o4-live-owner", email="o4-live-owner@example.test", password="pw")
        self.operator = User.objects.create_user(username="o4-live-operator", email="o4-live-operator@example.test", password="pw")
        self.participant = User.objects.create_user(username="o4-live-participant", email="o4-live-participant@example.test", password="pw")
        self.other_participant = User.objects.create_user(username="o4-live-other", email="secret-other@example.test", password="pw")
        self.assigned_only = User.objects.create_user(username="o4-live-assigned", email="o4-live-assigned@example.test", password="pw")
        self.space_supervisor = User.objects.create_user(username="o4-live-space", email="o4-live-space@example.test", password="pw")
        self.space = Organization.objects.create(name="O4 Space A", created_by=self.owner)
        self.other_space = Organization.objects.create(name="O4 Space B", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="O4 Live")
        self.other_activity = Activity.objects.create(space=self.other_space, created_by=self.owner, title="O4 Other")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Kinshasa → Matadi",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="Other occurrence",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.journey = Journey.objects.create(
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
            label="Embarquement",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        CheckpointAssignment.objects.create(
            checkpoint=self.checkpoint,
            profile=self.assigned_only,
            assigned_by=self.owner,
        )
        self.plan = PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="bus",
            label="Bus",
            required=True,
        )
        self.bus = PlacementUnit.objects.create(plan=self.plan, key="bus-2", label="Bus 2", kind="vehicle")
        self.seat = PlacementUnit.objects.create(plan=self.plan, parent=self.bus, key="seat-14", label="Siège 14", kind="seat")
        PlacementAssignment.objects.create(
            plan=self.plan,
            unit=self.seat,
            profile=self.participant,
            assigned_by=self.owner,
        )
        other_seat = PlacementUnit.objects.create(plan=self.plan, parent=self.bus, key="seat-15", label="Siège 15", kind="seat")
        PlacementAssignment.objects.create(
            plan=self.plan,
            unit=other_seat,
            profile=self.other_participant,
            assigned_by=self.owner,
        )
        self.queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            checkpoint=self.checkpoint,
            key="boarding",
            label="Embarquement",
        )
        self.entry = QueueEntry.objects.create(
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
        Access.objects.create(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.VALID,
        )
        Access.objects.create(
            beneficiary=self.other_participant,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        self.pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Bus",
            total_quantity=50,
        )
        CapacityReservation.objects.create(
            pool=self.pool,
            journey=self.journey,
            quantity=1,
            status=CapacityReservationStatus.COMMITTED,
            committed_at=self.now,
        )
        grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o4-live-test",
        )
        grant_space_role(
            profile=self.space_supervisor,
            space=self.space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.owner,
            source="o4-live-test",
        )

    def tearDown(self):
        reset_provider_registry()
        super().tearDown()

    def test_participant_live_is_personal_minimal_and_queue_aware(self):
        self.client.force_login(self.participant)
        before = DomainEventOutbox.objects.count()
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["perspective"], "participant")
        self.assertEqual(payload["phase"], "live")
        self.assertEqual(payload["placement"][0]["parent_unit"], "Bus 2")
        self.assertEqual(payload["placement"][0]["unit"], "Siège 14")
        self.assertEqual(payload["flow"]["next_checkpoint"]["label"], "Embarquement")
        self.assertEqual(payload["queue"][0]["status"], "waiting")
        self.assertEqual(payload["next_action"]["type"], "queue_wait")
        rendered = str(payload)
        self.assertNotIn(self.other_participant.email, rendered)
        self.assertNotIn("Siège 15", rendered)
        self.assertNotIn("assignments", rendered)
        self.assertNotIn("scanner", rendered)
        self.assertNotIn("credential", rendered.lower())
        self.assertNotIn("permissions", rendered.lower())
        self.assertEqual(DomainEventOutbox.objects.count(), before)

    def test_called_queue_entry_has_priority_over_placement(self):
        self.entry.status = QueueEntryStatus.CALLED
        self.entry.called_at = self.now
        self.entry.called_by = self.operator
        self.entry.save(update_fields=["status", "called_at", "called_by"])
        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        action = response.json()["next_action"]
        self.assertEqual(action["type"], "queue_called")
        self.assertEqual(action["checkpoint_id"], str(self.checkpoint.pk))

    def test_participant_and_assignment_only_idor_are_hidden(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.other_occurrence.pk]))
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.assigned_only)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 404)

    def test_operator_view_requires_authority_and_exposes_derived_operational_summaries(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["perspective"], "operator")
        self.assertIn("operational_readiness", payload)
        self.assertEqual(payload["queue"][0]["counts"]["waiting"], 2)
        self.assertEqual(payload["capacity"][0]["total"], 50)
        self.assertEqual(payload["capacity"][0]["committed"], 1)
        self.assertEqual(payload["checkpoints"][0]["assignment_count"], 1)
        self.assertEqual(payload["checkpoints"][0]["authorized_assignment_count"], 0)
        self.assertEqual(payload["operational_readiness"]["state"], "blocked")
        self.assertEqual(payload["next_action"]["reason"], "assigned_operator_without_effective_authority")

    def test_space_authority_is_scoped_to_its_space(self):
        self.client.force_login(self.space_supervisor)
        allowed = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["perspective"], "space")
        denied = self.client.get(reverse("operations_api:occurrence-live", args=[self.other_occurrence.pk]))
        self.assertEqual(denied.status_code, 404)

    def test_readiness_endpoint_uses_same_server_side_perspective(self):
        self.client.force_login(self.participant)
        participant = self.client.get(reverse("operations_api:occurrence-readiness", args=[self.occurrence.pk]))
        self.assertEqual(participant.status_code, 200)
        self.assertEqual(participant.json()["perspective"], "participant")
        keys = {row["key"] for row in participant.json()["contributors"]}
        self.assertNotIn("operations.authority", keys)
        self.assertNotIn("operations.assignments", keys)

        self.client.force_login(self.operator)
        operator = self.client.get(reverse("operations_api:occurrence-readiness", args=[self.occurrence.pk]))
        self.assertEqual(operator.status_code, 200)
        self.assertEqual(operator.json()["perspective"], "operator")
        operator_keys = {row["key"] for row in operator.json()["contributors"]}
        self.assertIn("operations.authority", operator_keys)

    def test_after_phase_never_pushes_participant_to_live_action(self):
        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.start_at = self.now - timedelta(hours=3)
        self.occurrence.end_at = self.now - timedelta(minutes=5)
        self.occurrence.save(update_fields=["status", "start_at", "end_at", "updated_at"])

        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["phase"], "after")
        self.assertEqual(payload["next_action"]["type"], "none")
        self.assertEqual(payload["next_action"]["reason"], "occurrence_completed")

    def test_m6_provider_unavailable_does_not_break_live_projection_or_fake_hazard(self):
        place = Place.objects.create(
            name="O4 Live Place",
            country_code="CD",
            latitude="-4.325000",
            longitude="15.322000",
            timezone="Africa/Kinshasa",
        )
        OccurrencePlace.objects.create(
            occurrence=self.occurrence,
            place=place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        set_provider_registry(
            ProviderRegistry(
                routing=NoOpRoutingProvider(),
                traffic=NoOpTrafficProvider(),
                weather=UnavailableWeatherProvider(),
            )
        )

        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["spatial"]["place"]["name"], "O4 Live Place")
        self.assertEqual(payload["spatial"]["hazards"], [])
        self.assertEqual(payload["spatial"]["mobility"]["status"], "destination_only")
