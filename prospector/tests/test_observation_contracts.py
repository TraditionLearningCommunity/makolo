from datetime import datetime, timedelta, timezone
from unittest import TestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.errors import ObservationContractError
from prospector.frontier import FrontierClaim
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
    ObservationReport,
    ObservationStatus,
    ObservedReference,
    make_handoff_key,
    observation_target_from_claim,
)


class ObservationContractTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now - timedelta(minutes=5),
            provider="test-index",
            attributes={"source_ref": "r1"},
        )
        self.target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/formation",
            kind="web_url",
            first_discovered_at=evidence.discovered_at,
            evidence=(evidence,),
            policy_context={"mission_key": "coverage"},
            observation_hints={"indexed_mime_type": "text/html"},
        )

    def claim(self, *, token="claim-a", generation=1):
        return FrontierClaim(
            claim_token=token,
            worker_id="worker-a",
            leased_until=self.now + timedelta(minutes=5),
            target=self.target,
            handoff_generation=generation,
        )

    def test_handoff_key_survives_claim_retry_but_changes_on_explicit_generation(self):
        first = observation_target_from_claim(
            self.claim(token="claim-a", generation=1),
            requested_at=self.now,
        )
        reclaimed = observation_target_from_claim(
            self.claim(token="claim-b", generation=1),
            requested_at=self.now + timedelta(minutes=6),
        )
        requeued = observation_target_from_claim(
            self.claim(token="claim-c", generation=2),
            requested_at=self.now + timedelta(hours=1),
        )

        self.assertEqual(first.handoff_key, reclaimed.handoff_key)
        self.assertNotEqual(first.handoff_key, requeued.handoff_key)

    def test_observation_target_discloses_only_technical_hints(self):
        target = observation_target_from_claim(
            self.claim(),
            requested_at=self.now,
        )
        self.assertEqual(target.observation_hints["indexed_mime_type"], "text/html")
        self.assertFalse(hasattr(target, "evidence"))
        self.assertFalse(hasattr(target, "policy_context"))
        self.assertFalse(hasattr(target, "activity_id"))
        self.assertFalse(hasattr(target, "requirement_id"))

    def test_deferred_receipt_requires_reason_and_retry(self):
        key = make_handoff_key(
            target_key=self.target.target_key,
            handoff_generation=1,
        )
        with self.assertRaises(ObservationContractError):
            ObservationReceipt(
                handoff_key=key,
                target_key=self.target.target_key,
                handoff_generation=1,
                disposition=ObservationDisposition.DEFERRED,
                received_at=self.now,
            )

        receipt = ObservationReceipt(
            handoff_key=key,
            target_key=self.target.target_key,
            handoff_generation=1,
            disposition=ObservationDisposition.DEFERRED,
            received_at=self.now,
            reason_code="observer.capacity",
            retry_at=self.now + timedelta(minutes=10),
        )
        self.assertEqual(receipt.disposition, ObservationDisposition.DEFERRED)

    def test_rejected_receipt_is_terminal_at_contract_level(self):
        key = make_handoff_key(
            target_key=self.target.target_key,
            handoff_generation=1,
        )
        receipt = ObservationReceipt(
            handoff_key=key,
            target_key=self.target.target_key,
            handoff_generation=1,
            disposition="rejected",
            received_at=self.now,
            reason_code="observer.unsupported_target",
        )
        self.assertEqual(receipt.disposition, ObservationDisposition.REJECTED)
        self.assertIsNone(receipt.retry_at)

    def test_report_contains_structure_not_page_body_or_business_facts(self):
        key = make_handoff_key(
            target_key=self.target.target_key,
            handoff_generation=1,
        )
        report = ObservationReport(
            handoff_key=key,
            target_key=self.target.target_key,
            handoff_generation=1,
            observation_ref="obs:test:1",
            status=ObservationStatus.OBSERVED,
            observed_at=self.now,
            requested_locator=self.target.locator,
            final_locator="https://example.test/formation",
            response_status=200,
            media_type="text/html",
            references=(
                ObservedReference(
                    relation="link",
                    locator="https://example.test/admission",
                    discovered_at=self.now,
                ),
                ObservedReference(
                    relation="sitemap",
                    locator="https://example.test/sitemap.xml",
                    discovered_at=self.now,
                ),
            ),
            technical_metadata={"redirect_count": 0},
        )
        self.assertEqual(len(report.references), 2)
        self.assertFalse(hasattr(report, "body"))
        self.assertFalse(hasattr(report, "content"))
        self.assertFalse(hasattr(report, "facts"))
        self.assertFalse(hasattr(report, "activity"))

    def test_failed_report_requires_failure_code(self):
        key = make_handoff_key(
            target_key=self.target.target_key,
            handoff_generation=1,
        )
        with self.assertRaises(ObservationContractError):
            ObservationReport(
                handoff_key=key,
                target_key=self.target.target_key,
                handoff_generation=1,
                observation_ref="obs:test:failed",
                status=ObservationStatus.FAILED,
                observed_at=self.now,
                requested_locator=self.target.locator,
            )
