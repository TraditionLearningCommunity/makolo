from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceStatus
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from domain_events.services import emit_domain_event
from journeys.models import ExternalBeneficiary, Journey, WorkflowKind
from notifications.models import Notification
from payments.models import PaymentObligationProcessingMode, PaymentObligationReason
from payments.obligation_services import create_payment_obligation

from .proactive_models import ProactivePreparationCursor
from .proactive_preparation import (
    apply_evaluation,
    evaluate_journey,
    reevaluate_cursor,
    run_proactive_preparation_cycle,
)


User = get_user_model()


class ProactiveJourneyR3Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="r3-journey-user",
            email="r3-journey-user@example.test",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Démarche R3",
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )

    def _baseline(self):
        evaluation = evaluate_journey(self.journey)
        self.assertIsNotNone(evaluation)
        self.assertEqual(evaluation.result.primary_action.identity.action_key, "continue_journey")
        outcome = apply_evaluation(evaluation)
        self.assertEqual(outcome.status, "baseline")
        return ProactivePreparationCursor.objects.get(journey=self.journey)

    def _create_payment_obligation(self):
        return create_payment_obligation(
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Frais de traitement",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            journey=self.journey,
            payer_profile=self.user,
            payee_platform=True,
            created_by=self.user,
            source_key=f"r3-journey-payment:{self.journey.pk}",
        )

    def test_journey_draft_to_payment_primary_action_is_material(self):
        cursor = self._baseline()
        self._create_payment_obligation()

        current = evaluate_journey(self.journey)
        self.assertEqual(current.result.primary_action.identity.action_key, "pay")
        outcome = apply_evaluation(current)

        self.assertTrue(outcome.material_changed)
        self.assertTrue(outcome.notification_created)
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 1)
        notification = Notification.objects.get(template_key="preparation.proactive")
        self.assertEqual(notification.metadata["journey_id"], str(self.journey.pk))
        self.assertNotIn("Frais de traitement", notification.message)

    def test_payment_owner_event_suppresses_duplicate_r3_notification(self):
        cursor = self._baseline()
        obligation = self._create_payment_obligation()
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.PAYMENT_OBLIGATION_CREATED,
            source_type="payment_obligation",
            source_id=obligation.pk,
        )

        current = evaluate_journey(self.journey)
        outcome = apply_evaluation(current, domain_event=event)

        self.assertTrue(outcome.material_changed)
        self.assertTrue(outcome.notification_suppressed)
        self.assertFalse(
            Notification.objects.filter(template_key="preparation.proactive").exists()
        )
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 1)

    def test_occurrence_cancelled_m6_attention_is_not_duplicated(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        Journey.objects.filter(pk=self.journey.pk).update(occurrence=occurrence)
        self.journey.refresh_from_db()
        cursor = self._baseline()

        Occurrence.objects.filter(pk=occurrence.pk).update(status=OccurrenceStatus.CANCELLED)
        event = emit_domain_event(
            event_type=DomainEventType.OCCURRENCE_CANCELLED,
            source_type="occurrence",
            source_id=occurrence.pk,
            idempotency_key=f"r3:test:occurrence-cancelled:{occurrence.pk}",
            activity_id=self.activity.pk,
            payload={
                "occurrence_id": str(occurrence.pk),
                "activity_id": str(self.activity.pk),
            },
            process_on_commit=False,
        )

        current = evaluate_journey(self.journey)
        self.assertEqual(current.result.primary_attention.actionability.value, "terminal")
        self.assertIsNone(current.result.primary_action)
        outcome = apply_evaluation(current, domain_event=event)

        self.assertTrue(outcome.material_changed)
        self.assertTrue(outcome.notification_suppressed)
        self.assertFalse(
            Notification.objects.filter(template_key="preparation.proactive").exists()
        )
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 1)

    def test_removed_permission_context_removes_watch_without_notification(self):
        cursor = self._baseline()
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        outcome = reevaluate_cursor(cursor)

        self.assertTrue(outcome.stale_removed)
        self.assertFalse(ProactivePreparationCursor.objects.filter(pk=cursor.pk).exists())
        self.assertFalse(
            Notification.objects.filter(template_key="preparation.proactive").exists()
        )

    def test_external_beneficiary_does_not_create_automatic_watch(self):
        external = ExternalBeneficiary.objects.create(
            display_name="Bénéficiaire externe R3",
            created_by=self.user,
        )
        Journey.objects.create(
            initiated_by=self.user,
            external_beneficiary=external,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        internal_journey_id = self.journey.pk
        self.journey.delete()

        stats = run_proactive_preparation_cycle(limit=10)

        self.assertFalse(ProactivePreparationCursor.objects.filter(journey_id=internal_journey_id).exists())
        self.assertFalse(ProactivePreparationCursor.objects.filter(journey__external_beneficiary=external).exists())
        self.assertEqual(stats["notifications_created"], 0)
