from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase, TestCase

from prospector.pilot import (
    PilotPolicy,
    PilotSnapshot,
    ProspectorPilotRunner,
    build_pilot_scorecard,
)
from prospector.runtime import RuntimeCycleStats
from prospector.source_contracts import (
    ProspectingMission,
    SourceRunResult,
)


class FakeSourceRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    async def run(self, *, source, mission):
        self.calls += 1
        if not self.results:
            raise AssertionError("unexpected source pass")
        return self.results.pop(0)


class FakeRuntime:
    def __init__(self, cycles):
        self.cycles = list(cycles)

    async def run_cycle(self):
        if not self.cycles:
            raise AssertionError("unexpected runtime cycle")
        return self.cycles.pop(0)


class PilotRunnerTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 19, tzinfo=timezone.utc)
        self.mission = ProspectingMission(
            mission_key="px8-test",
            issued_at=self.now,
            host_tlds=("cd",),
            path_terms=("formation",),
            max_candidates=10,
        )

    async def test_source_only_stops_when_source_is_exhausted(self):
        source_runner = FakeSourceRunner(
            [
                SourceRunResult(
                    source_name="test",
                    source_revision="r1",
                    received=3,
                    admitted=3,
                    exhausted=False,
                    next_cursor={"page": 1},
                ),
                SourceRunResult(
                    source_name="test",
                    source_revision="r1",
                    received=2,
                    admitted=2,
                    exhausted=True,
                    next_cursor={"page": 2},
                ),
            ]
        )
        runner = ProspectorPilotRunner(source_runner=source_runner)
        result = await runner.run(
            source=object(),
            mission=self.mission,
            policy=PilotPolicy(
                max_source_passes=5,
                max_runtime_cycles=0,
            ),
        )
        self.assertEqual(result.source_passes, 2)
        self.assertEqual(result.source_received, 5)
        self.assertEqual(result.source_admitted, 5)
        self.assertTrue(result.source_exhausted)
        self.assertEqual(result.runtime_cycles, 0)

    async def test_runtime_is_bounded_and_aggregated(self):
        source_runner = FakeSourceRunner(
            [
                SourceRunResult(
                    source_name="test",
                    source_revision="r1",
                    received=1,
                    admitted=1,
                    exhausted=True,
                    next_cursor={},
                )
            ]
        )
        runtime = FakeRuntime(
            [
                RuntimeCycleStats(claimed=2, completed=1, deferred=1),
                RuntimeCycleStats(claimed=1, suppressed=1),
                RuntimeCycleStats(claimed=0),
            ]
        )
        runner = ProspectorPilotRunner(
            source_runner=source_runner,
            runtime=runtime,
        )
        result = await runner.run(
            source=object(),
            mission=self.mission,
            policy=PilotPolicy(
                max_source_passes=1,
                max_runtime_cycles=5,
            ),
        )
        self.assertEqual(result.runtime_cycles, 3)
        self.assertEqual(result.runtime.claimed, 3)
        self.assertEqual(result.runtime.completed, 1)
        self.assertEqual(result.runtime.deferred, 1)
        self.assertEqual(result.runtime.suppressed, 1)

    async def test_runtime_cycles_without_runtime_are_rejected(self):
        runner = ProspectorPilotRunner(
            source_runner=FakeSourceRunner([]),
        )
        with self.assertRaises(ValueError):
            await runner.run(
                source=object(),
                mission=self.mission,
                policy=PilotPolicy(
                    max_source_passes=1,
                    max_runtime_cycles=1,
                ),
            )


class PilotScorecardTests(TestCase):
    def test_scorecard_uses_counts_and_marks_missing_downstream(self):
        now = datetime(2026, 9, 19, tzinfo=timezone.utc)
        mission = ProspectingMission(
            mission_key="px8-score",
            issued_at=now,
            host_tlds=("cd",),
            path_terms=("formation",),
            max_candidates=10,
        )
        before = PilotSnapshot(
            entry_count=2,
            discovery_count=3,
            evidence_count=3,
        )
        after = PilotSnapshot(
            entry_count=5,
            discovery_count=8,
            evidence_count=8,
            statuses={"ready": 5},
            evidence_methods={"external_index": 5},
            providers={"common_crawl": 5},
        )
        from prospector.pilot import PilotRunStats
        run = PilotRunStats(
            source_passes=1,
            source_received=5,
            source_admitted=5,
            source_exhausted=False,
            source_revision="CC-MAIN-test",
            runtime_cycles=0,
            runtime=RuntimeCycleStats(),
        )
        card = build_pilot_scorecard(
            mission=mission,
            policy=PilotPolicy(
                max_source_passes=1,
                max_runtime_cycles=0,
            ),
            run=run,
            before=before,
            after=after,
            started_at=now,
            finished_at=now,
        )
        self.assertEqual(card["frontier"]["new_entries"], 3)
        self.assertEqual(card["frontier"]["rediscoveries"], 2)
        self.assertFalse(card["feedback"]["downstream_evaluable"])
        self.assertIn(
            "observer_runtime_not_run",
            card["limitations"],
        )
        self.assertNotIn("locators", card)
