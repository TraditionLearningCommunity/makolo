import json
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.errors import ProspectorContractError
from prospector.providers.common_crawl import (
    COLLECTIONS_URL,
    CommonCrawlIndexSource,
    HttpResponse,
)
from prospector.source_contracts import ProspectingMission, SourceCheckpoint


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout_seconds):
        self.calls.append((url, dict(headers), timeout_seconds))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def ndjson(*records):
    return "\n".join(json.dumps(record) for record in records)


class CommonCrawlIndexSourceTests(IsolatedAsyncioTestCase):
    def mission(self, *, max_candidates=2):
        return ProspectingMission(
            mission_key="rdc-fragments",
            issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            host_tlds=("cd",),
            path_terms=("formation", "admission"),
            media_types=("text/html",),
            max_candidates=max_candidates,
        )

    async def test_discovers_latest_collection_and_returns_bounded_records(self):
        transport = FakeTransport(
            [
                HttpResponse(
                    200,
                    json.dumps([
                        {"id": "CC-MAIN-2026-34"},
                        {"id": "CC-MAIN-2026-30"},
                    ]),
                ),
                HttpResponse(
                    200,
                    ndjson(
                        {
                            "timestamp": "20260901010203",
                            "url": "https://uni.cd/formation/network",
                            "mime": "text/html",
                            "status": "200",
                            "digest": "sha1:A",
                            "filename": "crawl/a.warc.gz",
                            "offset": "10",
                            "length": "20",
                        },
                        {
                            "timestamp": "20260902010203",
                            "url": "https://school.cd/admission",
                            "mime": "text/html",
                            "status": "200",
                            "digest": "sha1:B",
                            "filename": "crawl/b.warc.gz",
                            "offset": "30",
                            "length": "40",
                        },
                    ),
                ),
            ]
        )
        source = CommonCrawlIndexSource(
            user_agent="Makolo Prospector test",
            transport=transport,
            max_requests_per_run=1,
        )

        batch = await source.discover(self.mission())

        self.assertEqual(batch.source_revision, "CC-MAIN-2026-34")
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(batch.records[0].provider, "common_crawl")
        self.assertIn("page=0", transport.calls[1][0])
        self.assertIn("pageSize=1", transport.calls[1][0])
        self.assertIn("matchType=domain", transport.calls[1][0])
        self.assertEqual(transport.calls[0][0], COLLECTIONS_URL)

    async def test_deduplicates_same_locator_inside_batch(self):
        record = {
            "timestamp": "20260901010203",
            "url": "https://uni.cd/formation/network",
            "mime": "text/html",
            "status": "200",
        }
        transport = FakeTransport(
            [
                HttpResponse(200, json.dumps([{"id": "CC-MAIN-2026-34"}])),
                HttpResponse(200, ndjson(record, record)),
            ]
        )
        source = CommonCrawlIndexSource(
            user_agent="Makolo Prospector test",
            transport=transport,
            max_requests_per_run=1,
        )
        batch = await source.discover(self.mission(max_candidates=10))
        self.assertEqual(len(batch.records), 1)

    async def test_exhausted_checkpoint_refreshes_only_when_new_crawl_exists(self):
        checkpoint = SourceCheckpoint(
            source_name="common_crawl_cdxj",
            mission_key="rdc-fragments",
            mission_fingerprint=self.mission().fingerprint,
            source_revision="CC-MAIN-2026-30",
            cursor={"selector_index": 1, "page": 0, "offset": 0},
            exhausted=True,
            updated_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        )
        transport = FakeTransport(
            [
                HttpResponse(200, json.dumps([{"id": "CC-MAIN-2026-34"}])),
                HttpResponse(400, "page out of range"),
            ]
        )
        source = CommonCrawlIndexSource(
            user_agent="Makolo Prospector test",
            transport=transport,
            max_requests_per_run=1,
        )
        batch = await source.discover(self.mission(), checkpoint=checkpoint)
        self.assertEqual(batch.source_revision, "CC-MAIN-2026-34")
        self.assertTrue(batch.exhausted)

    async def test_rejects_tld_only_bulk_scan(self):
        mission = ProspectingMission(
            mission_key="too-broad",
            issued_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            host_tlds=("com",),
        )
        source = CommonCrawlIndexSource(
            user_agent="Makolo Prospector test",
            transport=FakeTransport([]),
        )
        with self.assertRaises(ProspectorContractError):
            await source.discover(mission)
