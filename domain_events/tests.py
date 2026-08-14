from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from .contracts import DomainEventType
from .models import DomainEventConsumption, DomainEventOutbox, DomainEventStatus
from .registry import register_consumer, unregister_consumer
from .services import emit_domain_event, process_domain_events


class DomainEventOutboxTests(TestCase):
    def tearDown(self):
        unregister_consumer("tests.capture")
        unregister_consumer("tests.flaky")

    def test_emit_validates_contract_payload_and_idempotency(self):
        first = emit_domain_event(
            event_type=DomainEventType.JOURNEY_CONFIRMED,
            source_type="journey",
            source_id="abc",
            idempotency_key="test:journey:abc:confirmed",
            payload={"journey_id": "abc", "status": "confirmed"},
            process_on_commit=False,
        )
        second = emit_domain_event(
            event_type=DomainEventType.JOURNEY_CONFIRMED,
            source_type="journey",
            source_id="abc",
            idempotency_key="test:journey:abc:confirmed",
            payload={"journey_id": "abc", "status": "confirmed"},
            process_on_commit=False,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DomainEventOutbox.objects.count(), 1)

        with self.assertRaises(ValidationError):
            emit_domain_event(
                event_type="journey.do_something",
                source_type="journey",
                source_id="abc",
                idempotency_key="invalid:event",
                process_on_commit=False,
            )
        with self.assertRaises(ValidationError):
            emit_domain_event(
                event_type=DomainEventType.ACCESS_ISSUED,
                source_type="access",
                source_id="abc",
                idempotency_key="invalid:secret",
                payload={"qr_secret": "never-store-this"},
                process_on_commit=False,
            )

    def test_outbox_rolls_back_with_business_transaction(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                emit_domain_event(
                    event_type=DomainEventType.JOURNEY_SUBMITTED,
                    source_type="journey",
                    source_id="rollback",
                    idempotency_key="test:rollback",
                    payload={"journey_id": "rollback", "status": "submitted"},
                    process_on_commit=False,
                )
                raise RuntimeError("rollback")
        self.assertFalse(DomainEventOutbox.objects.filter(idempotency_key="test:rollback").exists())

    def test_processor_records_consumption_and_does_not_repeat_success(self):
        calls = []

        def capture(event):
            calls.append(str(event.pk))

        register_consumer(
            "tests.capture",
            capture,
            event_types={DomainEventType.JOURNEY_CONFIRMED},
        )
        event = emit_domain_event(
            event_type=DomainEventType.JOURNEY_CONFIRMED,
            source_type="journey",
            source_id="1",
            idempotency_key="test:processor:success",
            payload={"journey_id": "1", "status": "confirmed"},
            process_on_commit=False,
        )
        first = process_domain_events(limit=1)
        second = process_domain_events(limit=1)
        event.refresh_from_db()
        self.assertEqual(first["processed"], 1)
        self.assertEqual(second["claimed"], 0)
        self.assertEqual(calls, [str(event.pk)])
        self.assertEqual(event.status, DomainEventStatus.PROCESSED)
        self.assertEqual(
            DomainEventConsumption.objects.get(event=event, consumer="tests.capture").attempts,
            1,
        )

    def test_processor_failure_retries_only_failed_consumer(self):
        state = {"calls": 0}

        def flaky(event):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("temporary failure")

        register_consumer(
            "tests.flaky",
            flaky,
            event_types={DomainEventType.PAYMENT_FAILED},
        )
        event = emit_domain_event(
            event_type=DomainEventType.PAYMENT_FAILED,
            source_type="payment",
            source_id="1",
            idempotency_key="test:processor:retry",
            payload={"payment_id": "1", "status": "failed"},
            process_on_commit=False,
        )
        first = process_domain_events(limit=1)
        second = process_domain_events(limit=1)
        event.refresh_from_db()
        consumption = DomainEventConsumption.objects.get(event=event, consumer="tests.flaky")
        self.assertEqual(first["retry"], 1)
        self.assertEqual(second["processed"], 1)
        self.assertEqual(state["calls"], 2)
        self.assertEqual(consumption.attempts, 2)
        self.assertEqual(event.status, DomainEventStatus.PROCESSED)
