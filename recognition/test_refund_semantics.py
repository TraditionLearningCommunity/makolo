from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from domain_events.contracts import DomainEventType
from organizations.models import Organization

from .domain_event_consumer import RECOGNITION_EVENT_TYPES
from .ingest import record_signal
from .models import RecognitionAccount
from .runtime import run_default_recognition_cycle


class RecognitionRefundSemanticsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="recognition-refund-owner",
            email="recognition-refund@example.test",
            password="Recognition-2026!",
        )
        self.space = Organization.objects.create(name="Refund Space", created_by=self.owner)

    def test_payment_and_refund_are_distinct_positive_value_on_same_object(self):
        now = timezone.now().replace(microsecond=0)
        contributors = [{
            "subject_type": "space",
            "subject_id": str(self.space.pk),
            "causal_mode": "operate",
            "weight": "1",
        }]
        record_signal(
            signal_id="refund-contract-payment",
            signal_kind=DomainEventType.PAYMENT_SUCCEEDED,
            object_type="occurrence",
            object_id="occurrence-refund-contract",
            outcome_identity="payment:refund-contract:succeeded",
            occurred_at=now - timedelta(hours=2),
            available_at=now - timedelta(hours=2),
            values={"count": 1, "payment_id": "payment-refund-contract", "currency": "USD", "amount": "10"},
            contributors=contributors,
        )
        record_signal(
            signal_id="refund-contract-refund",
            signal_kind=DomainEventType.PAYMENT_REFUNDED,
            object_type="occurrence",
            object_id="occurrence-refund-contract",
            outcome_identity="payment:refund-contract:refunded",
            occurred_at=now - timedelta(hours=1),
            available_at=now - timedelta(hours=1),
            values={"count": 1, "payment_id": "payment-refund-contract", "currency": "USD", "amount": "10"},
            contributors=contributors,
        )

        result = run_default_recognition_cycle(now=now)
        account = RecognitionAccount.objects.get(space=self.space)
        self.assertEqual(result["issued_points"], 3)
        self.assertEqual(account.points_balance, 3)
        self.assertEqual(account.lifetime_earned, 3)

    def test_external_occurrence_cancellation_never_reverses_recognition(self):
        self.assertNotIn(DomainEventType.OCCURRENCE_CANCELLED, RECOGNITION_EVENT_TYPES)
        self.assertIn(DomainEventType.PAYMENT_REFUNDED, RECOGNITION_EVENT_TYPES)
