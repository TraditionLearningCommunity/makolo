"""Lot A: Journey N3 projects owner steps, not guessed milestones."""

from types import SimpleNamespace
from uuid import UUID

from django.test import SimpleTestCase

from core.api.detail_projections import _journey_step_summaries


class _RelatedRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class JourneyN3OwnerStepsTests(SimpleTestCase):
    def test_owner_steps_keep_status_and_dependencies_without_sensitive_fields(self):
        first_id = UUID("00000000-0000-0000-0000-000000000001")
        second_id = UUID("00000000-0000-0000-0000-000000000002")
        first = SimpleNamespace(
            pk=first_id,
            title="Déposer la demande",
            status="completed",
            kind="submission",
            position=0,
            description="Informations internes non publiées",
            dependencies=_RelatedRows([]),
        )
        second = SimpleNamespace(
            pk=second_id,
            title="Attendre la décision",
            status="pending",
            kind="decision",
            position=1,
            dependencies=_RelatedRows([SimpleNamespace(depends_on_id=first_id)]),
        )
        journey = SimpleNamespace(steps=_RelatedRows([first, second]))
        rows = _journey_step_summaries(journey)

        self.assertEqual([row["id"] for row in rows], [str(first_id), str(second_id)])
        self.assertEqual(rows[0]["status"], "completed")
        self.assertEqual(rows[1]["depends_on"], [str(first_id)])
        self.assertNotIn("description", rows[0])
        self.assertNotIn("created_by", rows[0])

    def test_no_steps_means_no_synthetic_progress(self):
        self.assertEqual(
            _journey_step_summaries(SimpleNamespace(steps=_RelatedRows([]))),
            [],
        )
