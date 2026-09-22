from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import AccessCredential, AccessStatus
from access.services import issue_access, render_access_credential
from accounts.models import User
from activities.models import (
    Activity,
    ActivityStatus,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
    OccurrenceTimingKind,
)
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind
from operations.models import (
    CheckpointStatus,
    OccurrenceCheckpoint,
    OccurrenceQueue,
    CheckpointAssignment,
    PlacementAssignment,
    PlacementPlan,
    PlacementUnit,
    QueueEntry,
    QueueEntryStatus,
)


PASSWORD = "Makolo!2026-Z6-DayOf"


class Z6PersonalDayOfAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.now = timezone.now()
        self.owner = self._user("z6-day-owner")
        self.participant = self._user("z6-day-participant")
        self.outsider = self._user("z6-day-outsider")
        self.activity = Activity.objects.create(
            title="Voyage Jour J Z6",
            created_by=self.owner,
            owner_profile=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Départ principal",
            start_at=self.now + timedelta(hours=4),
            end_at=self.now + timedelta(hours=7),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.place = Place.objects.create(
            name="Agence Makolo",
            address_line="Avenue du Départ",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            access_instructions="Présentez-vous à l’accueil.",
            latitude="-11.664700",
            longitude="27.479400",
            created_by=self.owner,
        )
        OccurrencePlace.objects.create(
            occurrence=self.occurrence,
            place=self.place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            source_key="z6:day-of",
        )
        self.credential = self.access.credentials.get()

    def _user(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@makolo.test",
            password=PASSWORD,
        )

    def _get(self):
        return self.client.get(
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/"
        )

    def test_day_of_requires_authentication_and_real_participant_relation(self):
        self.assertEqual(self._get().status_code, 401)

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self._get().status_code, 404)

        self.client.force_authenticate(self.owner)
        self.assertEqual(self._get().status_code, 404)

        self.client.force_authenticate(self.participant)
        self.assertEqual(
            self.client.get(
                f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/"
                f"?profile_id={self.outsider.pk}"
            ).status_code,
            400,
        )

    def test_before_root_answers_four_semantic_questions_without_fake_position(self):
        self.client.force_authenticate(self.participant)
        response = self._get()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["meta"]["projection"],
            "personal.occurrence.day_of",
        )
        data = payload["data"]
        self.assertEqual(data["situation"]["temporal_relation"], "before")
        self.assertEqual(
            data["situation"]["current_position"],
            {
                "state": "unknown",
                "truth": "unknown",
                "reason": "participant_position_not_observed",
            },
        )
        self.assertEqual(
            data["situation"]["representation"]["kind"],
            "timing",
        )
        self.assertEqual(data["spatial"]["destination"]["name"], self.place.name)
        self.assertEqual(data["spatial"]["destination"]["truth"], "planned")
        self.assertEqual(data["timing"]["truth"], "planned")
        self.assertEqual(data["spatial"]["mobility"]["truth"], "unknown")
        self.assertNotIn("live", data["links"])
        self.assertNotIn("open_live", data["capabilities"])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_future_valid_access_is_waiting_not_a_fake_regularization_blocker(self):
        self.client.force_authenticate(self.participant)
        data = self._get().json()["data"]

        self.assertEqual(data["situation"]["temporal_relation"], "before")
        self.assertEqual(data["situation"]["next"]["type"], "none")
        self.assertEqual(
            data["readiness"]["waiting"][0]["reason"],
            "participant_access_not_yet_valid",
        )
        self.assertEqual(data["readiness"]["blockers"], [])

    def test_access_is_composed_directly_but_credential_secret_stays_in_protected_depth(self):
        self.client.force_authenticate(self.participant)
        response = self._get()
        data = response.json()["data"]

        self.assertEqual(len(data["access"]), 1)
        row = data["access"][0]
        self.assertEqual(row["identity"]["id"], str(self.access.pk))
        self.assertEqual(row["state"], AccessStatus.VALID)
        self.assertFalse(row["usable"])
        self.assertTrue(row["credential"]["available"])
        self.assertFalse(row["credential"]["presentable"])
        self.assertEqual(
            row["links"]["detail"],
            f"/api/v1/me/accesses/{self.access.pk}/",
        )
        self.assertNotIn("credential", row["links"])
        self.assertNotIn("present_credential", row["capabilities"])

        rendered = str(response.json())
        self.assertNotIn(str(self.credential.public_id), rendered)
        self.assertNotIn(render_access_credential(self.credential), rendered)
        self.assertNotIn("payload", rendered.lower())

    def test_active_occurrence_hands_off_to_existing_operations_live(self):
        self.occurrence.start_at = self.now - timedelta(minutes=5)
        self.occurrence.end_at = self.now + timedelta(hours=2)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])
        self.access.valid_from = self.now - timedelta(minutes=10)
        self.access.valid_until = self.now + timedelta(hours=2)
        self.access.save(update_fields=["valid_from", "valid_until", "updated_at"])

        self.client.force_authenticate(self.participant)
        response = self._get()
        data = response.json()["data"]

        self.assertEqual(data["situation"]["temporal_relation"], "live")
        self.assertEqual(
            data["situation"]["representation"]["kind"],
            "live",
        )
        self.assertEqual(
            data["links"]["live"],
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/live/",
        )
        self.assertIn("open_live", data["capabilities"])
        self.assertNotIn("queue", data)
        self.assertNotIn("placement", data)
        self.assertNotIn("checkpoints", data)

    def test_operational_depths_are_composed_without_other_participant_identity(self):
        other = self._user("z6-day-other-participant")
        Journey.objects.create(
            initiated_by=other,
            beneficiary=other,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="boarding",
            label="Embarquement",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            checkpoint=checkpoint,
            key="boarding",
            label="Embarquement",
        )
        mine = QueueEntry.objects.create(
            queue=queue,
            profile=self.participant,
            sequence=2,
            status=QueueEntryStatus.WAITING,
            entered_by=self.participant,
        )
        QueueEntry.objects.create(
            queue=queue,
            profile=other,
            sequence=1,
            status=QueueEntryStatus.WAITING,
            entered_by=other,
        )
        plan = PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="bus",
            label="Bus",
            required=True,
        )
        bus = PlacementUnit.objects.create(
            plan=plan,
            key="bus-1",
            label="Bus 1",
            kind="vehicle",
        )
        seat = PlacementUnit.objects.create(
            plan=plan,
            parent=bus,
            key="seat-4",
            label="Siège 4",
            kind="seat",
        )
        PlacementAssignment.objects.create(
            plan=plan,
            unit=seat,
            profile=self.participant,
            assigned_by=self.owner,
        )

        self.occurrence.start_at = self.now - timedelta(minutes=5)
        self.occurrence.end_at = self.now + timedelta(hours=2)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])

        self.client.force_authenticate(self.participant)
        response = self._get()
        data = response.json()["data"]

        self.assertEqual(data["queue"][0]["id"], str(mine.pk))
        self.assertEqual(data["queue"][0]["state"], "waiting")
        self.assertEqual(data["placement"][0]["unit"], "Siège 4")
        self.assertEqual(data["placement"][0]["parent_unit"], "Bus 1")
        self.assertEqual(data["checkpoints"]["next"]["label"], "Embarquement")
        self.assertIn(data["readiness"]["state"], {"ready", "waiting", "action_required", "blocked"})
        rendered = str(data)
        self.assertNotIn(other.email, rendered)
        self.assertNotIn(other.username, rendered)
        self.assertNotIn("assignment_count", rendered)
        self.assertNotIn("capacity", data)

    def test_called_queue_becomes_the_personal_next_movement(self):
        checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="control",
            label="Contrôle",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            checkpoint=checkpoint,
            key="control",
            label="Contrôle",
        )
        entry = QueueEntry.objects.create(
            queue=queue,
            profile=self.participant,
            sequence=1,
            status=QueueEntryStatus.CALLED,
            entered_by=self.participant,
            called_at=self.now,
            called_by=self.owner,
        )
        self.occurrence.start_at = self.now - timedelta(minutes=5)
        self.occurrence.end_at = self.now + timedelta(hours=1)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])
        self.access.valid_from = self.now - timedelta(minutes=10)
        self.access.valid_until = self.now + timedelta(hours=1)
        self.access.save(update_fields=["valid_from", "valid_until", "updated_at"])

        self.client.force_authenticate(self.participant)
        data = self._get().json()["data"]

        self.assertEqual(data["situation"]["next"]["type"], "queue_called")
        self.assertEqual(data["queue"][0]["id"], str(entry.pk))
        self.assertEqual(data["queue"][0]["state"], "called")
        self.assertEqual(data["checkpoints"]["next"]["label"], "Contrôle")

    def test_after_phase_closes_operational_action_and_hands_off_to_history(self):
        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.start_at = self.now - timedelta(hours=3)
        self.occurrence.end_at = self.now - timedelta(minutes=5)
        self.occurrence.save(
            update_fields=["status", "start_at", "end_at", "updated_at"]
        )

        self.client.force_authenticate(self.participant)
        data = self._get().json()["data"]

        self.assertEqual(data["situation"]["temporal_relation"], "after")
        self.assertEqual(data["situation"]["next"]["type"], "none")
        self.assertEqual(data["completion"]["state"], "occurrence_ended")
        self.assertEqual(
            data["completion"]["links"]["history"],
            "/api/v1/me/history/",
        )
        self.assertNotIn("live", data["links"])
        self.assertNotIn("open_live", data["capabilities"])

    def test_date_only_keeps_calendar_truth_without_fake_midnight(self):
        target = (self.now + timedelta(days=3)).date()
        self.occurrence.timing_kind = OccurrenceTimingKind.DATE_ONLY
        self.occurrence.start_at = None
        self.occurrence.end_at = None
        self.occurrence.start_date = target
        self.occurrence.start_time = None
        self.occurrence.end_date = target
        self.occurrence.end_time = None
        self.occurrence.save(
            update_fields=[
                "timing_kind",
                "start_at",
                "end_at",
                "start_date",
                "start_time",
                "end_date",
                "end_time",
                "updated_at",
            ]
        )

        self.client.force_authenticate(self.participant)
        response = self._get()
        timing = response.json()["data"]["timing"]

        self.assertEqual(timing["kind"], OccurrenceTimingKind.DATE_ONLY)
        self.assertEqual(timing["start_date"], target.isoformat())
        self.assertIsNone(timing["start_at"])
        self.assertIsNone(timing["start_time"])
        self.assertNotIn("00:00", str(timing))

    def test_cancelled_occurrence_does_not_invent_movement(self):
        self.occurrence.status = OccurrenceStatus.CANCELLED
        self.occurrence.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.participant)
        response = self._get()
        situation = response.json()["data"]["situation"]

        self.assertEqual(situation["temporal_relation"], "cancelled")
        self.assertEqual(situation["representation"]["kind"], "cancellation")
        self.assertEqual(situation["next"]["type"], "none")
        self.assertEqual(situation["next"]["reason"], "occurrence_cancelled")
        self.assertNotIn("Rejoignez", situation["next"]["label"])

    def test_multi_role_profile_still_receives_participant_safe_day_of(self):
        self.activity.owner_profile = self.participant
        self.activity.save(update_fields=["owner_profile", "updated_at"])
        self.occurrence.start_at = self.now - timedelta(minutes=5)
        self.occurrence.end_at = self.now + timedelta(hours=2)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])

        self.client.force_authenticate(self.participant)
        response = self._get()
        rendered = str(response.json()).lower()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("assignment_count", rendered)
        self.assertNotIn("permissions", rendered)
        self.assertNotIn("scanner", rendered)
        self.assertNotIn(self.outsider.email, rendered)

    def test_assignment_without_participant_relation_does_not_open_day_of(self):
        assigned = self._user("z6-day-assigned-only")
        checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="assigned-only",
            label="Contrôle assigné",
            position=10,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        CheckpointAssignment.objects.create(
            checkpoint=checkpoint,
            profile=assigned,
            assigned_by=self.owner,
        )

        self.client.force_authenticate(assigned)
        self.assertEqual(self._get().status_code, 404)

    def test_arrival_phase_prefers_orientation_when_destination_is_known(self):
        self.occurrence.start_at = self.now + timedelta(minutes=20)
        self.occurrence.end_at = self.now + timedelta(hours=2)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])
        self.access.valid_from = self.now - timedelta(minutes=10)
        self.access.valid_until = self.now + timedelta(hours=2)
        self.access.save(update_fields=["valid_from", "valid_until", "updated_at"])

        self.client.force_authenticate(self.participant)
        data = self._get().json()["data"]
        self.assertEqual(data["situation"]["temporal_relation"], "arrival")
        self.assertEqual(
            data["situation"]["representation"]["kind"],
            "orientation",
        )
        self.assertEqual(data["spatial"]["destination"]["name"], self.place.name)

    def test_revoked_access_is_visible_as_context_but_cannot_present_credential(self):
        self.access.status = AccessStatus.REVOKED
        self.access._allow_status_transition = True
        self.access.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.participant)
        response = self._get()
        row = response.json()["data"]["access"][0]

        self.assertFalse(row["usable"])
        self.assertFalse(row["credential"]["presentable"])
        self.assertNotIn("credential", row["links"])
        self.assertNotIn("present_credential", row["capabilities"])
        self.assertEqual(
            response.json()["data"]["situation"]["representation"]["kind"],
            "access",
        )
