from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from journeys.collaboration_models import JourneyBlocker, JourneyBlockerStatus, JourneyStep, JourneyStepStatus
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestStatus, WorkflowKind
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import (
    add_requirement,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
)
from payments.models import (
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from readiness import ReadinessStatus, resolve_journey_readiness, resolve_many
from readiness.selectors import participant_readiness_queryset
from requirements.contracts import RequirementAssessmentState
from services.models import OpportunityPolicy, ServiceKind, ServiceRequirementStepLink
from services.requirement_services import assess_requirement
from services.services import create_service_details, create_service_journey


User = get_user_model()


class ReadinessEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ready-user", email="ready@example.test", password="x")
        self.other = User.objects.create_user(username="ready-other", email="ready-other@example.test", password="x")
        self.activity = Activity.objects.create(
            title="Activity générique READY",
            created_by=self.user,
            owner_profile=self.user,
            status=ActivityStatus.PUBLISHED,
        )

    def journey(self, **overrides):
        values = {
            "initiated_by": self.user,
            "beneficiary": self.user,
            "activity": self.activity,
            "workflow": WorkflowKind.REGISTRATION,
            "status": JourneyStatus.CONFIRMED,
        }
        values.update(overrides)
        return Journey.objects.create(**values)

    def loaded(self, journey):
        return participant_readiness_queryset(self.user).get(pk=journey.pk)

    def test_ready_generic_activity_and_complete_context(self):
        ready = resolve_journey_readiness(self.loaded(self.journey()), viewer=self.user)
        self.assertEqual(ready.status, ReadinessStatus.READY)
        self.assertTrue(ready.is_ready)
        complete = resolve_journey_readiness(
            self.loaded(self.journey(status=JourneyStatus.FULFILLED)),
            viewer=self.user,
        )
        self.assertEqual(complete.status, ReadinessStatus.COMPLETE)

    def test_participant_step_operator_waiting_and_blocker_are_distinct(self):
        participant = self.journey()
        JourneyStep.objects.create(
            journey=participant,
            title="Fournir une donnée",
            status=JourneyStepStatus.READY,
            created_by=self.user,
        )
        action = resolve_journey_readiness(self.loaded(participant), viewer=self.user)
        self.assertEqual(action.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertEqual(action.next_action.key, "complete_step")
        self.assertTrue(any(item.reason_code == "participant_step_required" for item in action.action_items))

        operator = self.journey()
        JourneyStep.objects.create(
            journey=operator,
            title="Validation opérateur",
            status=JourneyStepStatus.READY,
            created_by=self.other,
        )
        waiting = resolve_journey_readiness(self.loaded(operator), viewer=self.user)
        self.assertEqual(waiting.status, ReadinessStatus.WAITING)
        self.assertTrue(any(item.reason_code == "operator_step_pending" for item in waiting.waiting_items))

        blocked = self.journey()
        JourneyBlocker.objects.create(
            journey=blocked,
            title="Pièce indispensable",
            status=JourneyBlockerStatus.ACTIVE,
        )
        result = resolve_journey_readiness(self.loaded(blocked), viewer=self.user)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertEqual(result.blocking_items[0].reason_code, "journey_blocker_active")

    def test_draft_and_pending_request_have_different_ownership(self):
        draft = self.journey(status=JourneyStatus.DRAFT)
        action = resolve_journey_readiness(self.loaded(draft), viewer=self.user)
        self.assertEqual(action.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertEqual(action.next_action.key, "continue_journey")

        pending = self.journey(status=JourneyStatus.PENDING_APPROVAL)
        JourneyRequest.objects.create(journey=pending, requester=self.user, status=RequestStatus.PENDING)
        self.assertEqual(
            resolve_journey_readiness(self.loaded(pending), viewer=self.user).status,
            ReadinessStatus.WAITING,
        )
        rejected = self.journey(status=JourneyStatus.REJECTED)
        self.assertEqual(
            resolve_journey_readiness(self.loaded(rejected), viewer=self.user).status,
            ReadinessStatus.BLOCKED,
        )

    def test_payment_obligation_only_blocks_when_applicable(self):
        free = self.journey()
        self.assertEqual(
            resolve_journey_readiness(self.loaded(free), viewer=self.user).status,
            ReadinessStatus.READY,
        )
        payable = self.journey(status=JourneyStatus.PENDING_PAYMENT)
        PaymentObligation.objects.create(
            journey=payable,
            reason=PaymentObligationReason.OTHER,
            label="Frais requis",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            status=PaymentObligationStatus.PENDING,
            payer_profile=self.user,
            payee_platform=True,
        )
        result = resolve_journey_readiness(self.loaded(payable), viewer=self.user)
        self.assertEqual(result.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertTrue(any(item.reason_code == "payment_required" for item in result.action_items))

        for terminal_status in {PaymentObligationStatus.SATISFIED, PaymentObligationStatus.WAIVED}:
            journey = self.journey()
            PaymentObligation.objects.create(
                journey=journey,
                reason=PaymentObligationReason.OTHER,
                label=f"Frais {terminal_status}",
                amount=Decimal("10.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
                status=terminal_status,
                satisfied_at=timezone.now() if terminal_status == PaymentObligationStatus.SATISFIED else None,
                payer_profile=self.user,
                payee_platform=True,
            )
            self.assertEqual(
                resolve_journey_readiness(self.loaded(journey), viewer=self.user).status,
                ReadinessStatus.READY,
            )

    def test_access_capacity_and_occurrence_use_canonical_facts(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        journey = self.journey(occurrence=occurrence)
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=occurrence, total_quantity=5)
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=1,
            status=CapacityReservationStatus.COMMITTED,
            committed_at=timezone.now(),
        )
        Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=occurrence,
            journey=journey,
            status=AccessStatus.VALID,
        )
        self.assertEqual(
            resolve_journey_readiness(self.loaded(journey), viewer=self.user).status,
            ReadinessStatus.READY,
        )

        pending_access = self.journey(occurrence=occurrence)
        Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=occurrence,
            journey=pending_access,
            status=AccessStatus.PENDING,
        )
        self.assertEqual(
            resolve_journey_readiness(self.loaded(pending_access), viewer=self.user).status,
            ReadinessStatus.WAITING,
        )

        cancelled = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.CANCELLED,
        )
        self.assertEqual(
            resolve_journey_readiness(self.loaded(self.journey(occurrence=cancelled)), viewer=self.user).status,
            ReadinessStatus.BLOCKED,
        )

    def test_participant_scope_and_batch_resolver_are_query_free_after_prefetch(self):
        first = self.journey()
        second = self.journey(status=JourneyStatus.DRAFT)
        rows = list(participant_readiness_queryset(self.user).filter(pk__in=[first.pk, second.pk]))
        with self.assertNumQueries(0):
            results = resolve_many(rows, viewer=self.user)
        self.assertEqual(len(results), 2)
        with self.assertRaises(PermissionDenied):
            resolve_journey_readiness(rows[0], viewer=self.other)
        self.assertFalse(participant_readiness_queryset(self.other).filter(pk=first.pk).exists())


class ServiceReadinessTests(TestCase):
    def test_service_requirement_uses_assessment_and_concrete_step_without_copying_requirement(self):
        curator = User.objects.create_user(
            username="ready-curator",
            email="ready-curator@example.test",
            password="x",
            is_superuser=True,
            is_staff=True,
        )
        beneficiary = User.objects.create_user(
            username="ready-beneficiary",
            email="ready-beneficiary@example.test",
            password="x",
        )
        activity = Activity.objects.create(title="Service READY", created_by=curator, owner_profile=curator)
        service = create_service_details(
            activity=activity,
            actor=curator,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        opportunity = create_opportunity(actor=curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(
            opportunity=opportunity,
            actor=curator,
            title="Opportunity READY",
            issuer_name="Issuer",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=opportunity,
            actor=curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official",
            url="https://example.test/readiness",
            is_primary=True,
            verified=True,
        )
        add_requirement(
            revision=revision,
            actor=curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="CV",
            position=10,
        )
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=curator)
        journey = create_service_journey(
            service=service,
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            opportunity=opportunity,
        )
        assessment = journey.service_context.requirement_assessments.get()

        initial = resolve_journey_readiness(
            participant_readiness_queryset(beneficiary).get(pk=journey.pk),
            viewer=beneficiary,
        )
        self.assertEqual(initial.status, ReadinessStatus.WAITING)
        self.assertTrue(any(item.reason_code == "requirement_unassessed" for item in initial.waiting_items))

        assessment = assess_requirement(
            assessment=assessment,
            actor=curator,
            status=RequirementAssessmentState.PENDING,
        )
        step = JourneyStep.objects.create(
            journey=journey,
            title="Fournir le CV",
            status=JourneyStepStatus.READY,
            created_by=beneficiary,
        )
        ServiceRequirementStepLink.objects.create(
            assessment=assessment,
            journey_step=step,
            created_by=curator,
        )
        result = resolve_journey_readiness(
            participant_readiness_queryset(beneficiary).get(pk=journey.pk),
            viewer=beneficiary,
        )
        self.assertEqual(result.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertTrue(any(item.reason_code == "participant_step_required" for item in result.action_items))
        self.assertTrue(any(item.source == "requirements" for item in result.waiting_items))
