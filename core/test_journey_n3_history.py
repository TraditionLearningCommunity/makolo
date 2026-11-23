"""Journey N3 only presents authorized owner transition facts."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

from django.test import SimpleTestCase

from core.api.detail_projections import _journey_history


class _Transitions:
    def __init__(self, transitions):
        self.transitions = transitions

    def all(self):
        return self.transitions


class JourneyHistoryProjectionTests(SimpleTestCase):
    def test_chronology_excludes_private_reason_and_actor(self):
        at = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
        earlier = SimpleNamespace(
            pk=UUID("00000000-0000-0000-0000-000000000001"),
            from_status="draft",
            to_status="submitted",
            created_at=at,
            actor=SimpleNamespace(email="private@example.com"),
            reason="Confidential instructions",
        )
        later = SimpleNamespace(
            pk=UUID("00000000-0000-0000-0000-000000000002"),
            from_status="submitted",
            to_status="confirmed",
            created_at=at + timedelta(days=1),
            reason="Sensitive reason",
        )
        result = _journey_history(
            SimpleNamespace(transitions=_Transitions([earlier, later]))
        )
        self.assertEqual([item["state"] for item in result], ["confirmed", "submitted"])
        self.assertEqual(result[0]["label"], "Confirmée")
        self.assertEqual(set(result[0]), {"id", "label", "state", "at"})
        self.assertNotIn("Confidential", str(result))
        self.assertNotIn("private@", str(result))

    def test_history_is_bounded_and_no_transition_means_no_history(self):
        now = datetime(2026, 11, 10, tzinfo=timezone.utc)
        rows = [
            SimpleNamespace(
                pk=UUID(int=index + 1),
                from_status="draft",
                to_status="submitted",
                created_at=now + timedelta(minutes=index),
            )
            for index in range(20)
        ]
        journey = SimpleNamespace(transitions=_Transitions(rows))
        self.assertEqual(len(_journey_history(journey)), 10)
        self.assertEqual(_journey_history(
            SimpleNamespace(transitions=_Transitions([]))
        ), [])
