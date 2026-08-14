from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.services import grant_activity_role

from .models import JourneyRequest, JourneyStatus, RequestStatus, WorkflowKind
from .services import (
    approve_request,
    cancel_journey,
    confirm_journey,
    create_journey,
    create_request,
    expire_journey,
    expire_request,
    fulfill_journey,
    reject_request,
    request_approval,
    require_payment,
    submit_journey,
)


User = get_user_model()


class JourneyFixtureMixin:
    def build_fixture(self):
        self.initiator = User.objects.create_user(
            username="journey-initiator",
            email="journey-initiator@example.com",
            password="Journey-2026!",
        )
        self.beneficiary = User.objects.create_user(
            username="journey-beneficiary",
            email="journey-beneficiary@example.com",
            password="Journey-2026!",
        )
        self.decider = User.objects.create_superuser(
            username="journey-decider",
            email="journey-decider@example.com",
            password="Journey-2026!",
        )
        self.activity = Activity.objects.create(
            created_by=self.initiator,
            title="Makolo Journey Activity",
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=3),
        )

    def journey(self, workflow, **kwargs):
        return create_journey(
            initiated_by=kwargs.pop("initiated_by", self.initiator),
            beneficiary=kwargs.pop("beneficiary", self.beneficiary),
            activity=kwargs.pop("activity", self.activity),
            occurrence=kwargs.pop("occurrence", self.occurrence),
            workflow=workflow,
            **kwargs,
        )


class JourneyWorkflowTests(JourneyFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_purchase_paid_and_free_workflows(self):
        paid = self.journey(WorkflowKind.PURCHASE)
        require_payment(journey=paid)
        confirm_journey(journey=paid)
        fulfill_journey(journey=paid)
        paid.refresh_from_db()
        self.assertEqual(paid.status, JourneyStatus.FULFILLED)
        self.assertEqual(
            list(paid.transitions.values_list("to_status", flat=True)),
            [JourneyStatus.PENDING_PAYMENT, JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED],
        )

        free = self.journey(WorkflowKind.PURCHASE)
        confirm_journey(journey=free)
        fulfill_journey(journey=free)
        free.refresh_from_db()
        self.assertEqual(free.status, JourneyStatus.FULFILLED)

    def test_registration_and_reservation_need_no_payment(self):
        for workflow in (WorkflowKind.REGISTRATION, WorkflowKind.RESERVATION):
            journey = self.journey(workflow)
            submit_journey(journey=journey, actor=self.initiator)
            confirm_journey(journey=journey)
            fulfill_journey(journey=journey)
            journey.refresh_from_db()
            self.assertEqual(journey.status, JourneyStatus.FULFILLED)

    def test_approval_workflow_uses_request_then_continues(self):
        journey = self.journey(WorkflowKind.REGISTRATION)
        submit_journey(journey=journey, actor=self.initiator)
        request = create_request(journey=journey, requester=self.initiator, message="Merci de valider")
        self.assertEqual(request.status, RequestStatus.PENDING)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.PENDING_APPROVAL)

        approve_request(request=request, actor=self.decider, comment="OK")
        request.refresh_from_db()
        journey.refresh_from_db()
        self.assertEqual(request.status, RequestStatus.APPROVED)
        self.assertEqual(journey.status, JourneyStatus.APPROVED)

        confirm_journey(journey=journey)
        fulfill_journey(journey=journey)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.FULFILLED)

    def test_invitation_can_be_approved_and_confirmed(self):
        journey = self.journey(WorkflowKind.INVITATION)
        submit_journey(journey=journey, actor=self.initiator)
        request = create_request(journey=journey, requester=self.initiator)
        approve_request(request=request, actor=self.decider)
        confirm_journey(journey=journey)
        fulfill_journey(journey=journey)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.FULFILLED)

    def test_invalid_transition_and_arbitrary_status_write_are_rejected(self):
        journey = self.journey(WorkflowKind.REGISTRATION)
        with self.assertRaises(ValidationError):
            fulfill_journey(journey=journey)

        journey.status = JourneyStatus.FULFILLED
        with self.assertRaises(ValidationError):
            journey.save()

    def test_cancel_and_expire_are_controlled_and_idempotent(self):
        journey = self.journey(WorkflowKind.RESERVATION)
        cancel_journey(journey=journey, actor=self.initiator)
        cancel_journey(journey=journey, actor=self.initiator)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.CANCELLED)

        expiring = self.journey(
            WorkflowKind.REGISTRATION,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        expire_journey(journey=expiring)
        expire_journey(journey=expiring)
        expiring.refresh_from_db()
        self.assertEqual(expiring.status, JourneyStatus.EXPIRED)

    def test_activity_occurrence_consistency_and_distinct_beneficiary(self):
        other = Activity.objects.create(created_by=self.initiator, title="Other Activity")
        other_occurrence = Occurrence.objects.create(
            activity=other,
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
        )
        with self.assertRaises(ValidationError):
            create_journey(
                initiated_by=self.initiator,
                beneficiary=self.beneficiary,
                activity=self.activity,
                occurrence=other_occurrence,
                workflow=WorkflowKind.REGISTRATION,
            )

        journey = self.journey(WorkflowKind.REGISTRATION)
        self.assertNotEqual(journey.initiated_by_id, journey.beneficiary_id)


class JourneyRequestSecurityTests(JourneyFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def _pending_request(self, activity=None, occurrence=None):
        activity = activity or self.activity
        occurrence = occurrence or self.occurrence
        journey = create_journey(
            initiated_by=self.initiator,
            beneficiary=self.beneficiary,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
        )
        submit_journey(journey=journey, actor=self.initiator)
        return create_request(journey=journey, requester=self.initiator)

    def test_reject_and_double_decision(self):
        request = self._pending_request()
        reject_request(request=request, actor=self.decider, comment="Non")
        request.refresh_from_db()
        request.journey.refresh_from_db()
        self.assertEqual(request.status, RequestStatus.REJECTED)
        self.assertEqual(request.journey.status, JourneyStatus.REJECTED)
        with self.assertRaises(ValidationError):
            approve_request(request=request, actor=self.decider)

    def test_wrong_actor_cannot_decide(self):
        request = self._pending_request()
        with self.assertRaises(PermissionDenied):
            approve_request(request=request, actor=self.beneficiary)
        request.refresh_from_db()
        self.assertEqual(request.status, RequestStatus.PENDING)

    def test_activity_isolation_for_local_manager(self):
        manager = User.objects.create_user(
            username="activity-a-manager",
            email="activity-a-manager@example.com",
            password="Journey-2026!",
        )
        grant_activity_role(profile=manager, activity=self.activity)

        other = Activity.objects.create(created_by=self.initiator, title="Activity B")
        other_occurrence = Occurrence.objects.create(
            activity=other,
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
        )
        request = self._pending_request(activity=other, occurrence=other_occurrence)
        with self.assertRaises(PermissionDenied):
            approve_request(request=request, actor=manager)

    def test_request_expiration_synchronizes_journey(self):
        journey = self.journey(WorkflowKind.REGISTRATION)
        submit_journey(journey=journey, actor=self.initiator)
        request = create_request(
            journey=journey,
            requester=self.initiator,
            expires_at=timezone.now() + timedelta(seconds=1),
        )
        future = timezone.now() + timedelta(minutes=1)
        expire_request(request=request, now=future)
        request.refresh_from_db()
        journey.refresh_from_db()
        self.assertEqual(request.status, RequestStatus.EXPIRED)
        self.assertEqual(journey.status, JourneyStatus.EXPIRED)
