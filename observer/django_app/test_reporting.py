from __future__ import annotations

from datetime import datetime, timedelta, timezone

from asgiref.sync import async_to_sync
from django.test import TestCase

from prospector.observation_contracts import (
    ObservationStatus,
    ObservationTarget,
    make_handoff_key,
)

from observer.contracts import ObservationOutcome, ObservationTrigger
from observer.django_store import (
    absorb_observation_target,
    get_or_create_observation_series,
)
from observer.identifiers import make_reference_key
from observer.prospector_reporting import (
    build_observation_report,
    submit_observation_report,
)

from .models import (
    Observation,
    ObservationAttempt,
    ObservedReference as ObservedReferenceRow,
)


class RecordingSink:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.reports = []

    async def submit_report(self, report):
        self.reports.append(report)
        if self.fail:
            raise RuntimeError("sink unavailable")
        return {"accepted": True}


class ObserverProspectorReportingTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)
        self.target_key = "web_url:v1:" + ("f" * 64)
        self.target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=1,
            ),
            target_key=self.target_key,
            handoff_generation=1,
            locator="https://example.test/resource",
            kind="web_url",
            requested_at=self.now,
            observation_hints={},
        )
        self.handoff = absorb_observation_target(
            self.target,
            absorbed_at=self.now,
        )[0]
        self.series = get_or_create_observation_series(
            self.target,
            profile_key="public-http",
            profile_fingerprint="public-http:test",
        )[0]

    def observation(self, *, outcome=ObservationOutcome.OBSERVED):
        failure_code = ""
        retry_at = None
        response_status = 200
        if outcome is ObservationOutcome.FAILED:
            failure_code = "http.timeout"
            retry_at = self.now + timedelta(minutes=1)
            response_status = None
        return Observation.objects.create(
            series=self.series,
            source_handoff=self.handoff,
            trigger=ObservationTrigger.HANDOFF.value,
            lifecycle="finalized",
            outcome=outcome.value,
            started_at=self.now,
            observed_at=self.now + timedelta(seconds=1),
            completed_at=self.now + timedelta(seconds=2),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=response_status,
            failure_code=failure_code,
            retry_at=retry_at,
            profile_ref="public-http",
            profile_fingerprint="public-http:test",
            policy_fingerprint="observer-http:test",
        )

    def test_report_contains_only_bounded_technical_feedback(self):
        observation = self.observation()
        ObservationAttempt.objects.create(
            observation=observation,
            ordinal=1,
            strategy="direct_http",
            lifecycle="finalized",
            outcome="succeeded",
            started_at=self.now,
            completed_at=self.now + timedelta(seconds=1),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=200,
            redirect_count=1,
            wire_bytes=120,
            decoded_bytes=100,
        )
        ObservedReferenceRow.objects.create(
            observation=observation,
            reference_key=make_reference_key(
                relation="redirect",
                kind="web_url",
                locator="https://example.test/final",
            ),
            relation="redirect",
            locator="https://example.test/final",
            kind="web_url",
            discovered_at=self.now + timedelta(seconds=1),
            attributes={"media_type": "text/html"},
        )

        report = build_observation_report(
            observation.observation_ref
        )

        self.assertEqual(report.status, ObservationStatus.OBSERVED)
        self.assertEqual(report.handoff_key, self.handoff.handoff_key)
        self.assertEqual(report.references[0].relation, "redirect")
        self.assertEqual(
            report.technical_metadata,
            {
                "attempt_count": 1,
                "artifact_count": 0,
                "revalidated_artifact_count": 0,
                "redirect_count": 1,
                "wire_bytes": 120,
                "decoded_bytes": 100,
                "strategy": "direct_http",
            },
        )
        self.assertFalse(hasattr(report, "body"))
        self.assertFalse(hasattr(report, "content"))

    def test_failed_report_preserves_retry_without_business_meaning(self):
        observation = self.observation(
            outcome=ObservationOutcome.FAILED
        )

        report = build_observation_report(
            observation.observation_ref
        )

        self.assertEqual(report.status, ObservationStatus.FAILED)
        self.assertEqual(report.failure_code, "http.timeout")
        self.assertEqual(
            report.retry_at,
            self.now + timedelta(minutes=1),
        )

    def test_submission_marks_reported_only_after_sink_success(self):
        observation = self.observation()
        sink = RecordingSink()

        result = async_to_sync(submit_observation_report)(
            observation.observation_ref,
            sink=sink,
        )

        self.assertEqual(result, {"accepted": True})
        observation.refresh_from_db()
        self.assertIsNotNone(observation.prospector_reported_at)
        self.assertEqual(len(sink.reports), 1)

    def test_failed_submission_never_marks_reported(self):
        observation = self.observation()
        sink = RecordingSink(fail=True)

        with self.assertRaisesRegex(RuntimeError, "sink unavailable"):
            async_to_sync(submit_observation_report)(
                observation.observation_ref,
                sink=sink,
            )

        observation.refresh_from_db()
        self.assertIsNone(observation.prospector_reported_at)
