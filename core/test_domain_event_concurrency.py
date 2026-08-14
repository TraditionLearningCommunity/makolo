import threading
import unittest
import uuid

from django.db import connection, connections
from django.test import TransactionTestCase

from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer, unregister_consumer
from domain_events.services import emit_domain_event, process_domain_events

from .models import DomainEventConsumption


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL locking test")
class DomainEventProcessorConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def tearDown(self):
        unregister_consumer("tests.concurrent")

    def test_two_processors_do_not_deliver_same_event_twice(self):
        barrier = threading.Barrier(2)
        calls = []
        calls_lock = threading.Lock()
        outcomes = []

        def consumer(event):
            with calls_lock:
                calls.append(str(event.pk))

        register_consumer(
            "tests.concurrent",
            consumer,
            event_types={DomainEventType.REQUEST_CREATED},
        )
        request_id = str(uuid.uuid4())
        event = emit_domain_event(
            event_type=DomainEventType.REQUEST_CREATED,
            source_type="request",
            source_id=request_id,
            idempotency_key="test:processor:concurrent",
            payload={"request_id": request_id, "status": "pending"},
            process_on_commit=False,
        )

        def worker():
            connections["default"].close()
            barrier.wait(timeout=10)
            outcomes.append(process_domain_events(batch_size=1, limit=1))
            connections["default"].close()

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(calls, [str(event.pk)])
        self.assertEqual(sum(item["claimed"] for item in outcomes), 1)
        self.assertEqual(
            DomainEventConsumption.objects.filter(event=event, consumer="tests.concurrent").count(),
            1,
        )
