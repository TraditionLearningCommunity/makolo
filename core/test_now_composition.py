from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase

from core.api.now_composition_projection import _visible_dependency_situation
from readiness import ReadinessStatus


class NowRealCompositionTests(SimpleTestCase):
    def setUp(self):
        self.dossier_id = uuid4()
        self.a = uuid4()
        self.b = uuid4()
        self.dossier = SimpleNamespace(pk=self.dossier_id, title="Dossier mobilité")
        self.observed_at = datetime(2026, 10, 9, tzinfo=timezone.utc)

    def readiness(self, *, satisfied=False, hidden=False, status=ReadinessStatus.BLOCKED):
        visible = [] if hidden else [
            SimpleNamespace(
                dependent_journey_id=self.a,
                dependent_label="Étape A",
                required_journey_id=self.b,
                required_label="Étape B",
                is_satisfied=satisfied,
            )
        ]
        return SimpleNamespace(
            dossier=self.dossier,
            status=status,
            visible_dependencies=visible,
            is_partial=hidden,
        )

    def test_owner_visible_unsatisfied_dependency_yields_s5(self):
        data = _visible_dependency_situation(
            self.readiness(), observed_at=self.observed_at,
        )
        self.assertEqual(data["source"], {"kind": "dossier", "id": str(self.dossier_id)})
        self.assertEqual(data["relations"][0]["kind"], "dependency")
        self.assertEqual(
            data["relations"][0]["member_ids"], [str(self.a), str(self.b)],
        )
        self.assertEqual(data["response"]["type"], "understand")
        self.assertEqual(data["turn"]["type"], "none")
        self.assertEqual(data["consequence"]["state"], "known")
        self.assertEqual(data["business_actions"], [])

    def test_hidden_dependency_never_creates_or_counts_a_member(self):
        self.assertIsNone(_visible_dependency_situation(
            self.readiness(hidden=True), observed_at=self.observed_at,
        ))

    def test_satisfied_or_nonblocked_dependency_is_not_a_current_s5(self):
        self.assertIsNone(_visible_dependency_situation(
            self.readiness(satisfied=True), observed_at=self.observed_at,
        ))
        self.assertIsNone(_visible_dependency_situation(
            self.readiness(status=ReadinessStatus.READY),
            observed_at=self.observed_at,
        ))
