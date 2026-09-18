from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.adapters.crawlee_queue import (
    CrawleeObservationInbox,
    CrawleeQueuePolicy,
)
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationTarget,
    make_handoff_key,
)


class FakeQueue:
    def __init__(self, *, total=0, handled=0, existing=None, add_result=object()):
        self.total = total
        self.handled = handled
        self.existing = existing
        self.add_result = add_result
        self.added = []

    async def get_request(self, unique_key):
        return self.existing

    async def get_total_count(self):
        return self.total

    async def get_handled_count(self):
        return self.handled

    async def add_request(self, request):
        self.added.append(request)
        return self.add_result


class CrawleeObservationInboxTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        target_key = "web_url:v1:" + ("a" * 64)
        self.target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=target_key,
                handoff_generation=1,
            ),
            target_key=target_key,
            handoff_generation=1,
            locator="https://example.test/resource?x=1",
            kind="web_url",
            requested_at=self.now - timedelta(seconds=1),
            observation_hints={"indexed_mime_type": "text/html"},
        )
        self.policy = CrawleeQueuePolicy(
            queue_name="makolo-observer-test",
            max_pending_requests=3,
            capacity_retry_seconds=60,
        )

    def inbox(self, queue):
        return CrawleeObservationInbox(
            request_queue=queue,
            policy=self.policy,
            clock=lambda: self.now,
        )

    async def test_new_handoff_uses_handoff_key_as_crawlee_unique_key(self):
        queue = FakeQueue()
        receipt = await self.inbox(queue).submit(self.target)

        self.assertEqual(receipt.disposition, ObservationDisposition.ACCEPTED)
        self.assertEqual(len(queue.added), 1)
        request = queue.added[0]
        self.assertEqual(request.unique_key, self.target.handoff_key)
        self.assertEqual(request.url, self.target.locator)
        self.assertEqual(request.label, "makolo-observation")
        makolo = request.user_data["makolo"]
        self.assertEqual(makolo["target_key"], self.target.target_key)
        self.assertEqual(makolo["handoff_generation"], 1)
        self.assertEqual(
            makolo["observation_hints"],
            {"indexed_mime_type": "text/html"},
        )
        self.assertNotIn("policy_context", makolo)
        self.assertNotIn("evidence", makolo)

    async def test_existing_request_is_already_accepted_even_when_queue_is_full(self):
        queue = FakeQueue(
            total=100,
            handled=0,
            existing=object(),
        )
        receipt = await self.inbox(queue).submit(self.target)

        self.assertEqual(
            receipt.disposition,
            ObservationDisposition.ALREADY_ACCEPTED,
        )
        self.assertEqual(queue.added, [])

    async def test_capacity_backpressure_defers_before_enqueue(self):
        queue = FakeQueue(total=10, handled=7)
        receipt = await self.inbox(queue).submit(self.target)

        self.assertEqual(receipt.disposition, ObservationDisposition.DEFERRED)
        self.assertEqual(receipt.reason_code, "observer.capacity")
        self.assertEqual(
            receipt.retry_at,
            self.now + timedelta(seconds=60),
        )
        self.assertEqual(queue.added, [])

    async def test_zero_capacity_is_a_valid_hard_pause(self):
        policy = CrawleeQueuePolicy(
            queue_name="makolo-observer-test",
            max_pending_requests=0,
            capacity_retry_seconds=30,
        )
        queue = FakeQueue()
        inbox = CrawleeObservationInbox(
            request_queue=queue,
            policy=policy,
            clock=lambda: self.now,
        )
        receipt = await inbox.submit(self.target)

        self.assertEqual(receipt.disposition, ObservationDisposition.DEFERRED)
        self.assertEqual(queue.added, [])

    async def test_duplicate_race_from_add_request_maps_to_already_accepted(self):
        queue = FakeQueue(add_result=None)
        receipt = await self.inbox(queue).submit(self.target)

        self.assertEqual(
            receipt.disposition,
            ObservationDisposition.ALREADY_ACCEPTED,
        )
