from datetime import datetime, timezone
from unittest import TestCase

from prospector.errors import ProspectorContractError
from prospector.source_contracts import ProspectingMission


class ProspectingMissionTests(TestCase):
    def test_mission_is_coverage_intent_not_site_list(self):
        mission = ProspectingMission(
            mission_key="rdc-action-fragments",
            issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            host_tlds=(".CD",),
            languages=("FR",),
            path_terms=("admission", "formation"),
            max_candidates=250,
            context={"geography": "CD"},
        )
        self.assertEqual(mission.host_tlds, ("cd",))
        self.assertEqual(mission.languages, ("fr",))
        self.assertEqual(mission.max_candidates, 250)
        self.assertFalse(hasattr(mission, "sites"))

    def test_mission_requires_bounded_selector(self):
        with self.assertRaises(ProspectorContractError):
            ProspectingMission(
                mission_key="unbounded",
                issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            )

    def test_fingerprint_changes_when_coverage_changes(self):
        base = ProspectingMission(
            mission_key="coverage",
            issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            host_tlds=("cd",),
            path_terms=("formation",),
        )
        changed = ProspectingMission(
            mission_key="coverage",
            issued_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
            host_tlds=("cd",),
            path_terms=("formation", "bourse"),
        )
        self.assertNotEqual(base.fingerprint, changed.fingerprint)
