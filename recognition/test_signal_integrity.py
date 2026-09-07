from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .ingest import record_signal


class RecognitionSignalIntegrityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="recognition-signal-integrity",
            email="recognition-signal-integrity@example.test",
            password="test-pass-2026",
        )
        self.occurred_at = timezone.now().replace(microsecond=0) - timedelta(hours=2)
        self.first_available_at = self.occurred_at + timedelta(hours=1)

    def _record(self, *, available_at=None, count=1):
        return record_signal(
            signal_id="signal-integrity-1",
            signal_kind="access.used",
            object_type="occurrence",
            object_id="signal-integrity-occurrence",
            outcome_identity="signal-integrity-outcome",
            occurred_at=self.occurred_at,
            available_at=available_at or self.first_available_at,
            values={"count": count},
            contributors=[{
                "subject_type": "profile",
                "subject_id": str(self.user.pk),
                "causal_mode": "enable",
                "weight": "1",
            }],
            source_ref="test:signal-integrity",
        )

    def test_identical_retry_keeps_first_observation_time(self):
        first = self._record()
        retry = self._record(available_at=self.first_available_at + timedelta(hours=5))
        self.assertEqual(retry.pk, first.pk)
        retry.refresh_from_db()
        self.assertEqual(retry.available_at, self.first_available_at)

    def test_same_outcome_with_different_semantics_is_rejected(self):
        self._record(count=1)
        with self.assertRaises(ValidationError):
            self._record(count=2)

    def test_persisted_signal_semantics_cannot_be_mutated(self):
        signal = self._record()
        signal.values = {"count": "2"}
        with self.assertRaises(ValidationError):
            signal.save()
