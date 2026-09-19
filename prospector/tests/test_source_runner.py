from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.source_contracts import (
    IndexedResource,
    ProspectingMission,
    SourceBatch,
)
from prospector.source_runner import IndexProspector


class FakeFrontier:
    def __init__(self, fail_on=None):
        self.admitted = []
        self.fail_on = fail_on

    async def admit(self, candidate):
        if self.fail_on is not None and len(self.admitted) == self.fail_on:
            raise RuntimeError("boom")
        self.admitted.append(candidate)
        return candidate


class FakeCheckpoints:
    def __init__(self):
        self.current = None

    async def load(self, **kwargs):
        if self.current and self.current.mission_fingerprint == kwargs["mission_fingerprint"]:
            return self.current
        return None

    async def save(self, checkpoint):
        self.current = checkpoint


class FakeSource:
    name = "fake_index"

    async def discover(self, mission, *, checkpoint=None):
        return SourceBatch(
            source_name=self.name,
            source_revision="rev-1",
            records=(
                IndexedResource(
                    provider=self.name,
                    locator="https://example.test/a",
                    observed_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
                    source_revision="rev-1",
                    source_ref="r1",
                    mime_type="text/html",
                ),
                IndexedResource(
                    provider=self.name,
                    locator="https://example.test/b",
                    observed_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
                    source_revision="rev-1",
                    source_ref="r2",
                ),
            ),
            next_cursor={"page": 1},
            exhausted=False,
        )


class IndexProspectorTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.mission = ProspectingMission(
            mission_key="test",
            issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            host_tlds=("test",),
            path_terms=("action",),
        )

    async def test_admits_index_records_with_provenance_then_advances_checkpoint(self):
        frontier = FakeFrontier()
        checkpoints = FakeCheckpoints()
        runner = IndexProspector(frontier=frontier, checkpoints=checkpoints)

        result = await runner.run(source=FakeSource(), mission=self.mission)

        self.assertEqual(result.received, 2)
        self.assertEqual(result.admitted, 2)
        self.assertEqual(len(frontier.admitted), 2)
        self.assertEqual(
            frontier.admitted[0].evidence[0].provider,
            "fake_index",
        )
        self.assertEqual(checkpoints.current.cursor["page"], 1)

    async def test_does_not_advance_checkpoint_if_frontier_admission_fails(self):
        frontier = FakeFrontier(fail_on=1)
        checkpoints = FakeCheckpoints()
        runner = IndexProspector(frontier=frontier, checkpoints=checkpoints)

        with self.assertRaises(RuntimeError):
            await runner.run(source=FakeSource(), mission=self.mission)

        self.assertIsNone(checkpoints.current)
        self.assertEqual(len(frontier.admitted), 1)
