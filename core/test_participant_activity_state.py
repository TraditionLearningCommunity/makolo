from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, PaymentMode
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestPurpose, WorkflowKind

from .participant_presentation import resolve_participant_activity_state
from .participant_selectors import participant_state_context


User = get_user_model()


class ParticipantActivityStateTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="state-profile",
            email="state-profile@task17.test",
            password="test-pass",
        )
        self.other = User.objects.create_user(
            username="state-other",
            email="state-other@task17.test",
            password="test-pass",
        )
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            title="Activité canonique",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )

    def resolve(self, *, availability_state="available", availability_label="Disponible"):
        context = participant_state_context(self.profile, [self.occurrence])
        return resolve_participant_activity_state(
            profile=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            context=context,
            availability_state=availability_state,
            availability_label=availability_label,
            acquisition_label="S’inscrire",
            acquisition_url="/acquire/",
            detail_url="/detail/",
            now=self.now,
        )

    def journey(self, *, status=JourneyStatus.DRAFT, workflow=WorkflowKind.REGISTRATION):
        return Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
            status=status,
        )

    def test_no_interaction_keeps_normal_acquisition(self):
        state = self.resolve()
        self.assertEqual(state.participant_state, "none")
        self.assertEqual(state.primary_action, "S’inscrire")
        self.assertEqual(state.primary_url, "/acquire/")

    def test_pending_journey_request_is_presented_as_sent_request(self):
        journey = self.journey(status=JourneyStatus.PENDING_APPROVAL, workflow=WorkflowKind.ORDER_APPROVAL)
        JourneyRequest.objects.create(
            journey=journey,
            requester=self.profile,
            purpose=RequestPurpose.APPROVAL,
            expires_at=self.now + timedelta(hours=3),
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "request_pending")
        self.assertEqual(state.label, "Demande envoyée")
        self.assertEqual(
            state.primary_url,
            reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
        )

    def test_active_capacity_hold_exposes_real_expiry(self):
        journey = self.journey(status=JourneyStatus.DRAFT, workflow=WorkflowKind.RESERVATION)
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Places",
            total_quantity=10,
        )
        expires = self.now + timedelta(minutes=20)
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=1,
            status=CapacityReservationStatus.HELD,
            expires_at=expires,
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "capacity_held")
        self.assertEqual(state.label, "Place retenue temporairement")
        self.assertEqual(state.expires_at, expires)
        self.assertTrue(state.secondary_label.startswith("Jusqu’à "))

    def test_expired_hold_does_not_block_acquisition_without_active_journey(self):
        journey = self.journey(status=JourneyStatus.EXPIRED, workflow=WorkflowKind.RESERVATION)
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Places expirées",
            total_quantity=10,
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=1,
            status=CapacityReservationStatus.HELD,
            expires_at=self.now - timedelta(minutes=1),
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "none")
        self.assertEqual(state.primary_url, "/acquire/")

    def test_pending_commerce_payment_uses_live_canonical_route(self):
        journey = self.journey(status=JourneyStatus.PENDING_PAYMENT, workflow=WorkflowKind.PURCHASE)
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.profile,
            payment_mode=PaymentMode.UPFRONT,
            currency="USD",
            subtotal=Decimal("12.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("12.00"),
            expires_at=self.now + timedelta(hours=1),
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "payment_pending")
        self.assertEqual(state.label, "Paiement en attente")
        self.assertEqual(state.primary_action, "Reprendre le paiement")
        self.assertEqual(
            state.primary_url,
            reverse("payments:commerce-start", kwargs={"order_pk": order.pk}),
        )

    def test_closed_activity_lifecycle_keeps_pending_payment_as_history_only(self):
        cases = (
            (ActivityStatus.CANCELLED, OccurrenceStatus.CANCELLED, "cancelled"),
            (ActivityStatus.COMPLETED, OccurrenceStatus.COMPLETED, "completed"),
        )
        for index, (activity_status, occurrence_status, expected_availability) in enumerate(cases):
            with self.subTest(activity_status=activity_status):
                activity = Activity.objects.create(
                    title=f"Activité fermée {index}",
                    created_by=self.other,
                    owner_profile=self.other,
                    status=activity_status,
                )
                occurrence = Occurrence.objects.create(
                    activity=activity,
                    start_at=self.now + timedelta(days=3 + index),
                    end_at=self.now + timedelta(days=3 + index, hours=1),
                    status=occurrence_status,
                )
                journey = Journey.objects.create(
                    initiated_by=self.profile,
                    beneficiary=self.profile,
                    activity=activity,
                    occurrence=occurrence,
                    workflow=WorkflowKind.PURCHASE,
                    status=JourneyStatus.PENDING_PAYMENT,
                )
                order = CommerceOrder.objects.create(
                    journey=journey,
                    buyer=self.profile,
                    payment_mode=PaymentMode.UPFRONT,
                    currency="USD",
                    subtotal=Decimal("12.00"),
                    discount_total=Decimal("0.00"),
                    total=Decimal("12.00"),
                    expires_at=self.now + timedelta(hours=1),
                )
                context = participant_state_context(self.profile, [occurrence])
                state = resolve_participant_activity_state(
                    profile=self.profile,
                    activity=activity,
                    occurrence=occurrence,
                    context=context,
                    acquisition_label="S’inscrire",
                    acquisition_url="/bad-acquisition/",
                    detail_url="/detail/",
                    now=self.now,
                )
                self.assertEqual(state.availability, expected_availability)
                self.assertEqual(state.participant_state, "payment_pending")
                self.assertEqual(state.label, "Paiement en attente")
                self.assertEqual(
                    state.primary_url,
                    reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                )
                self.assertNotEqual(
                    state.primary_url,
                    reverse("payments:commerce-start", kwargs={"order_pk": order.pk}),
                )
                self.assertNotEqual(state.primary_action, "Reprendre le paiement")

    def test_access_states_are_historical_and_never_fall_back_to_acquisition(self):
        cases = (
            (AccessStatus.VALID, "access_valid", "Vous avez accès"),
            (AccessStatus.USED, "access_used", "Accès utilisé"),
            (AccessStatus.REVOKED, "access_revoked", "Accès révoqué"),
            (AccessStatus.CANCELLED, "access_cancelled", "Accès annulé"),
            (AccessStatus.EXPIRED, "access_expired", "Accès expiré"),
        )
        for status, expected_state, expected_label in cases:
            with self.subTest(status=status):
                Access.objects.all().delete()
                access = Access.objects.create(
                    beneficiary=self.profile,
                    activity=self.activity,
                    occurrence=self.occurrence,
                    status=status,
                )
                state = self.resolve()
                self.assertEqual(state.participant_state, expected_state)
                self.assertEqual(state.label, expected_label)
                self.assertNotEqual(state.primary_url, "/acquire/")
                self.assertEqual(
                    state.primary_url,
                    reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
                )

    def test_valid_access_wins_over_stale_pending_order(self):
        journey = self.journey(status=JourneyStatus.PENDING_PAYMENT, workflow=WorkflowKind.PURCHASE)
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.profile,
            payment_mode=PaymentMode.UPFRONT,
            subtotal=Decimal("9.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("9.00"),
        )
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            status=AccessStatus.VALID,
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "access_valid")
        self.assertEqual(
            state.primary_url,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )
        self.assertNotEqual(state.primary_action, "Reprendre le paiement")

    def test_cancelled_activity_keeps_personal_access_but_blocks_acquisition(self):
        cancelled = Activity.objects.create(
            title="Activité annulée",
            owner_profile=self.other,
            status=ActivityStatus.CANCELLED,
        )
        occurrence = Occurrence.objects.create(
            activity=cancelled,
            start_at=self.now + timedelta(days=1),
            end_at=self.now + timedelta(days=1, hours=1),
            status=OccurrenceStatus.CANCELLED,
        )
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=cancelled,
            occurrence=occurrence,
            status=AccessStatus.VALID,
        )
        context = participant_state_context(self.profile, [occurrence])
        state = resolve_participant_activity_state(
            profile=self.profile,
            activity=cancelled,
            occurrence=occurrence,
            context=context,
            acquisition_label="S’inscrire",
            acquisition_url="/bad-acquisition/",
            detail_url="/detail/",
            now=self.now,
        )
        self.assertEqual(state.availability, "cancelled")
        self.assertEqual(state.participant_state, "access_valid")
        self.assertEqual(
            state.primary_url,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )

    def test_sold_out_without_personal_relation_never_offers_acquisition(self):
        state = self.resolve(availability_state="sold_out", availability_label="Complet")
        self.assertEqual(state.availability, "sold_out")
        self.assertEqual(state.availability_label, "Complet")
        self.assertNotEqual(state.primary_url, "/acquire/")

    def test_activity_without_event_uses_same_resolver(self):
        self.assertFalse(hasattr(self.activity, "event_vertical"))
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "access_valid")
        self.assertEqual(state.primary_url, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))

    def test_other_profiles_state_is_not_loaded(self):
        Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        state = self.resolve()
        self.assertEqual(state.participant_state, "none")
        self.assertEqual(state.primary_url, "/acquire/")

    def test_batch_context_query_count_does_not_scale_per_occurrence(self):
        occurrences = [self.occurrence]
        for index in range(4):
            occurrence = Occurrence.objects.create(
                activity=self.activity,
                label=f"Date {index}",
                start_at=self.now + timedelta(days=3 + index),
                end_at=self.now + timedelta(days=3 + index, hours=1),
                status=OccurrenceStatus.SCHEDULED,
            )
            self.journey(status=JourneyStatus.DRAFT)
            occurrences.append(occurrence)
        with CaptureQueriesContext(connection) as queries:
            participant_state_context(self.profile, occurrences)
        self.assertLessEqual(len(queries), 6)
