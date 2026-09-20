from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from observer.adapters.crawlee_inbox import (
    observation_target_from_crawlee_request,
)
from prospector.adapters.crawlee_queue import (
    CrawleeObservationInbox,
    CrawleeQueuePolicy,
)
from prospector.observation_contracts import (
    ObservationTarget,
    make_handoff_key,
)


class FakeQueue:
    def __init__(self):
        self.added = []

    async def get_request(self, unique_key):
        return None

    async def get_total_count(self):
        return 0

    async def get_handled_count(self):
        return 0

    async def add_request(self, request):
        self.added.append(request)
        return object()


class ObserverCrawleeRoundTripTests(IsolatedAsyncioTestCase):
    async def test_observation_target_round_trip_is_lossless(self):
        now = datetime(
            2026,
            9,
            19,
            18,
            0,
            tzinfo=timezone.utc,
        )
        target_key = "web_url:v1:" + ("a" * 64)
        target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=target_key,
                handoff_generation=3,
            ),
            target_key=target_key,
            handoff_generation=3,
            locator="https://example.test/resource?x=1",
            kind="web_url",
            requested_at=now - timedelta(seconds=1),
            observation_hints={
                "indexed_mime_type": "text/html",
            },
        )
        queue = FakeQueue()
        inbox = CrawleeObservationInbox(
            request_queue=queue,
            policy=CrawleeQueuePolicy(
                queue_name="observer-round-trip",
                max_pending_requests=10,
                capacity_retry_seconds=60,
            ),
            clock=lambda: now,
        )

        await inbox.submit(target)

        self.assertEqual(len(queue.added), 1)
        restored = observation_target_from_crawlee_request(
            queue.added[0]
        )
        self.assertEqual(restored, target)
