from datetime import datetime, timedelta, timezone
from unittest import TestCase

from prospector.contracts import (
    CONTRACT_VERSION,
    ProspectingCandidate,
    ProspectingEvidence,
    ProspectingTarget,
)
from prospector.errors import ProspectorContractError


class ProspectingContractTests(TestCase):
    def setUp(self):
        self.evidence = ProspectingEvidence(
            method="web_graph",
            discovered_at=datetime(2026, 9, 18, 8, 30, tzinfo=timezone.utc),
            source_target_key="web:https://example.test/",
            attributes={"relation": "link"},
        )

    def test_candidate_requires_provenance(self):
        with self.assertRaises(ProspectorContractError):
            ProspectingCandidate(
                locator="https://example.test/programs",
                kind="web_url",
                evidence=(),
            )

    def test_candidate_rejects_empty_locator(self):
        with self.assertRaises(ProspectorContractError):
            ProspectingCandidate(locator="  ", kind="web_url", evidence=(self.evidence,))

    def test_evidence_requires_timezone_aware_datetime(self):
        with self.assertRaises(ProspectorContractError):
            ProspectingEvidence(
                method="external_index",
                discovered_at=datetime(2026, 9, 18, 8, 30),
                provider="example-index",
            )

    def test_datetimes_are_normalized_to_utc(self):
        plus_two = timezone(timedelta(hours=2))
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=datetime(2026, 9, 18, 10, 30, tzinfo=plus_two),
            provider="example-index",
        )
        self.assertEqual(evidence.discovered_at.utcoffset(), timedelta(0))
        self.assertEqual(evidence.discovered_at.hour, 8)

    def test_metadata_mappings_are_read_only_copies(self):
        source = {"campaign": "rdc-training"}
        candidate = ProspectingCandidate(
            locator="https://example.test/programs",
            kind="web_url",
            evidence=(self.evidence,),
            policy_context=source,
        )
        source["campaign"] = "mutated"
        self.assertEqual(candidate.policy_context["campaign"], "rdc-training")
        with self.assertRaises(TypeError):
            candidate.policy_context["campaign"] = "other"

    def test_target_identity_is_explicit_and_versioned(self):
        target = ProspectingTarget(
            target_key="web:https://example.test/programs",
            locator="https://example.test/programs",
            kind="web_url",
            first_discovered_at=self.evidence.discovered_at,
            evidence=(self.evidence,),
        )
        self.assertEqual(target.contract_version, CONTRACT_VERSION)
        self.assertEqual(target.target_key, "web:https://example.test/programs")

    def test_contracts_do_not_assign_business_semantics(self):
        candidate = ProspectingCandidate(
            locator="https://example.test/scholarships",
            kind="web_url",
            evidence=(self.evidence,),
            observation_hints={"expected_media_type": "text/html"},
        )
        self.assertFalse(hasattr(candidate, "activity_id"))
        self.assertFalse(hasattr(candidate, "occurrence_id"))
        self.assertFalse(hasattr(candidate, "opportunity_id"))
