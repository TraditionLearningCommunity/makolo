from types import SimpleNamespace

from django.test import SimpleTestCase

from .signal_contracts import resolve_recognition_object, sanitize_event_values


class RecognitionObjectPoolResolutionTests(SimpleTestCase):
    def _event(self, event_type, source_id, payload, *, activity_id=None):
        return SimpleNamespace(
            event_type=event_type,
            source_type="payment" if event_type.startswith("payment.") else "source",
            source_id=source_id,
            pk=source_id,
            space_id=None,
            activity_id=activity_id,
            payload=payload,
        )

    def test_payments_for_same_occurrence_roll_up_to_same_recognition_object(self):
        event_a = self._event(
            "payment.succeeded",
            "payment-a",
            {"payment_id": "payment-a", "occurrence_id": "occurrence-1", "amount": "10", "currency": "USD"},
        )
        event_b = self._event(
            "payment.succeeded",
            "payment-b",
            {"payment_id": "payment-b", "occurrence_id": "occurrence-1", "amount": "25", "currency": "USD"},
        )
        values_a = sanitize_event_values(event_a)
        values_b = sanitize_event_values(event_b)
        self.assertEqual(resolve_recognition_object(event_a, values_a), ("occurrence", "occurrence-1"))
        self.assertEqual(resolve_recognition_object(event_b, values_b), ("occurrence", "occurrence-1"))

    def test_refund_is_new_outcome_but_stays_on_same_action_object(self):
        payment = self._event(
            "payment.succeeded",
            "payment-a",
            {"payment_id": "payment-a", "journey_id": "journey-1", "amount": "10", "currency": "USD"},
        )
        refund = self._event(
            "payment.refunded",
            "payment-a",
            {"payment_id": "payment-a", "journey_id": "journey-1", "amount": "10", "currency": "USD"},
        )
        self.assertEqual(resolve_recognition_object(payment, sanitize_event_values(payment)), ("journey", "journey-1"))
        self.assertEqual(resolve_recognition_object(refund, sanitize_event_values(refund)), ("journey", "journey-1"))

    def test_opportunity_revision_pool_belongs_to_opportunity_not_revision(self):
        event = self._event(
            "opportunity.revision.published",
            "revision-9",
            {"opportunity_id": "opportunity-3", "revision_id": "revision-9", "version": 9},
        )
        self.assertEqual(resolve_recognition_object(event, sanitize_event_values(event)), ("opportunity", "opportunity-3"))
