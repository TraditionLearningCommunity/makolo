from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from journeys.models import ExternalBeneficiary, Journey, JourneyStatus, WorkflowKind

from .models import PlacementAssignment, PlacementPlan, PlacementUnit
from .placement_services import assign_placement, move_placement, unassign_placement


User = get_user_model()


class O1PlacementTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="o1-owner",
            email="o1-placement-owner@example.test",
            password="test-password",
        )
        self.operator = User.objects.create_user(
            username="o1-operator",
            email="o1-placement-operator@example.test",
            password="test-password",
        )
        self.participant = User.objects.create_user(
            username="o1-participant",
            email="o1-placement-participant@example.test",
            password="test-password",
        )
        self.other_participant = User.objects.create_user(
            username="o1-other",
            email="o1-placement-other@example.test",
            password="test-password",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="O1 Placement Activity",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session O1",
            start_at=self.now + timedelta(days=1),
            end_at=self.now + timedelta(days=1, hours=2),
        )
        grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o1-test",
        )
        self.plan = PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="seating",
            label="Placement salle",
            required=True,
        )
        self.section = PlacementUnit.objects.create(
            plan=self.plan,
            key="room-b",
            label="Salle B",
            kind="room",
            position=1,
        )
        self.seat_b14 = PlacementUnit.objects.create(
            plan=self.plan,
            parent=self.section,
            key="b14",
            label="B14",
            kind="seat",
            position=14,
            exclusive=True,
        )
        self.seat_b15 = PlacementUnit.objects.create(
            plan=self.plan,
            parent=self.section,
            key="b15",
            label="B15",
            kind="seat",
            position=15,
            exclusive=True,
        )
        self.participant_journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.other_journey = Journey.objects.create(
            initiated_by=self.other_participant,
            beneficiary=self.other_participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.external = ExternalBeneficiary.objects.create(
            display_name="Invité externe",
            email="external-o1@example.test",
            created_by=self.owner,
        )
        self.external_journey = Journey.objects.create(
            initiated_by=self.owner,
            external_beneficiary=self.external,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.INVITATION,
            status=JourneyStatus.CONFIRMED,
        )

    def test_models_support_plan_hierarchy_and_exactly_one_beneficiary(self):
        self.assertEqual(self.plan.occurrence, self.occurrence)
        self.assertEqual(self.seat_b14.parent, self.section)

        with self.assertRaises(ValidationError):
            PlacementAssignment(
                plan=self.plan,
                unit=self.seat_b14,
                assigned_by=self.operator,
            ).full_clean()
        with self.assertRaises(ValidationError):
            PlacementAssignment(
                plan=self.plan,
                unit=self.seat_b14,
                profile=self.participant,
                external_beneficiary=self.external,
                assigned_by=self.operator,
            ).full_clean()

    def test_assignment_rejects_unit_from_another_plan(self):
        other_plan = PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="transport",
            label="Transport",
        )
        other_unit = PlacementUnit.objects.create(plan=other_plan, key="bus-2", label="Bus 2")
        with self.assertRaises(ValidationError):
            PlacementAssignment(
                plan=self.plan,
                unit=other_unit,
                profile=self.participant,
                assigned_by=self.operator,
            ).full_clean()

    def test_assign_move_unassign_preserves_history_and_emits_events(self):
        assignment = assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b14,
            profile=self.participant,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.PLACEMENT_ASSIGNED,
                source_id=str(assignment.pk),
            ).exists()
        )

        moved = move_placement(actor=self.operator, assignment=assignment, unit=self.seat_b15)
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.ended_at)
        self.assertIsNone(moved.ended_at)
        self.assertEqual(moved.unit, self.seat_b15)
        self.assertEqual(PlacementAssignment.objects.filter(plan=self.plan, profile=self.participant).count(), 2)
        self.assertTrue(DomainEventOutbox.objects.filter(event_type=DomainEventType.PLACEMENT_CHANGED).exists())

        unassign_placement(actor=self.operator, assignment=moved)
        moved.refresh_from_db()
        self.assertIsNotNone(moved.ended_at)
        self.assertFalse(
            PlacementAssignment.objects.filter(
                plan=self.plan,
                profile=self.participant,
                ended_at__isnull=True,
            ).exists()
        )
        self.assertTrue(DomainEventOutbox.objects.filter(event_type=DomainEventType.PLACEMENT_UNASSIGNED).exists())

    def test_exclusive_unit_refuses_double_active_assignment(self):
        assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b14,
            profile=self.participant,
        )
        with self.assertRaises(ValidationError):
            assign_placement(
                actor=self.operator,
                plan=self.plan,
                unit=self.seat_b14,
                profile=self.other_participant,
            )

    def test_external_beneficiary_is_supported(self):
        assignment = assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b14,
            external_beneficiary=self.external,
        )
        self.assertIsNone(assignment.profile_id)
        self.assertEqual(assignment.external_beneficiary, self.external)

    def test_participant_sees_only_own_occurrence_placement(self):
        own = assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b14,
            profile=self.participant,
        )
        assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b15,
            profile=self.other_participant,
        )
        self.client.force_login(self.participant)
        response = self.client.get(
            reverse("operations_api:occurrence-placement-me", args=[self.occurrence.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(str(response.json()[0]["id"]), str(own.pk))
        self.assertEqual(response.json()[0]["unit_path"], ["Salle B", "B14"])
        self.assertNotIn("email", response.content.decode().lower())

    def test_operator_can_assign_move_and_unassign_through_api(self):
        self.client.force_login(self.operator)
        create_response = self.client.post(
            reverse("operations_api:placement-assignments", args=[self.plan.pk]),
            data={"unit_id": str(self.seat_b14.pk), "profile_id": str(self.participant.pk)},
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        assignment_id = create_response.json()["id"]

        move_response = self.client.patch(
            reverse("operations_api:placement-assignment-detail", args=[assignment_id]),
            data={"unit_id": str(self.seat_b15.pk)},
            content_type="application/json",
        )
        self.assertEqual(move_response.status_code, 200)
        moved_id = move_response.json()["id"]
        self.assertNotEqual(str(moved_id), str(assignment_id))

        delete_response = self.client.delete(
            reverse("operations_api:placement-assignment-detail", args=[moved_id])
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_operator_api_supports_external_beneficiary(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("operations_api:placement-assignments", args=[self.plan.pk]),
            data={
                "unit_id": str(self.seat_b14.pk),
                "external_beneficiary_id": str(self.external.pk),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["beneficiary"]["type"], "external_beneficiary")
        self.assertNotIn(self.external.email, response.content.decode())

    def test_unauthorized_participant_cannot_manage_or_view_operator_plan(self):
        self.client.force_login(self.participant)
        plan_response = self.client.get(
            reverse("operations_api:occurrence-placement-plans", args=[self.occurrence.pk])
        )
        self.assertEqual(plan_response.status_code, 403)
        assign_response = self.client.post(
            reverse("operations_api:placement-assignments", args=[self.plan.pk]),
            data={"unit_id": str(self.seat_b14.pk), "profile_id": str(self.participant.pk)},
            content_type="application/json",
        )
        self.assertEqual(assign_response.status_code, 403)

    def test_cross_activity_idor_is_refused(self):
        other_activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Other Activity",
        )
        other_occurrence = Occurrence.objects.create(
            activity=other_activity,
            start_at=self.now + timedelta(days=2),
        )
        other_plan = PlacementPlan.objects.create(
            occurrence=other_occurrence,
            key="group",
            label="Groupes",
        )
        other_unit = PlacementUnit.objects.create(plan=other_plan, key="g-a", label="Groupe A")
        other_assignment = PlacementAssignment.objects.create(
            plan=other_plan,
            unit=other_unit,
            profile=self.participant,
            assigned_by=self.owner,
        )

        self.client.force_login(self.operator)
        response = self.client.patch(
            reverse("operations_api:placement-assignment-detail", args=[other_assignment.pk]),
            data={"unit_id": str(other_unit.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_api_rejects_profile_not_linked_to_occurrence(self):
        outsider = User.objects.create_user(
            username="o1-outsider",
            email="o1-placement-outsider@example.test",
            password="test-password",
        )
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("operations_api:placement-assignments", args=[self.plan.pk]),
            data={"unit_id": str(self.seat_b14.pk), "profile_id": str(outsider.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_historical_occurrence_without_placement_remains_valid(self):
        legacy_occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Sans placement",
            start_at=self.now - timedelta(days=10),
            end_at=self.now - timedelta(days=10) + timedelta(hours=1),
        )
        self.client.force_login(self.participant)
        response = self.client.get(
            reverse("operations_api:occurrence-placement-me", args=[legacy_occurrence.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_placement_event_payload_is_minimal_and_non_sensitive(self):
        assignment = assign_placement(
            actor=self.operator,
            plan=self.plan,
            unit=self.seat_b14,
            profile=self.participant,
        )
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.PLACEMENT_ASSIGNED,
            source_id=str(assignment.pk),
        )
        self.assertEqual(event.payload["subject_type"], "profile")
        payload_text = str(event.payload).lower()
        self.assertNotIn("email", payload_text)
        self.assertNotIn("credential", payload_text)
        self.assertNotIn("qr", payload_text)
