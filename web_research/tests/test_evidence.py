from datetime import datetime, timezone
from unittest import TestCase

from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    EVIDENCE_FINDINGS_ATTRIBUTE,
    EvidenceNormalizer,
    EvidenceState,
    WebResearchCandidate,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)


NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


def _mission():
    return ResearchMission(
        primary_family=ResearchFamily.REQUIREMENT,
        subject="Mechanical Engineering Scholarship",
        questions=("Quelle est la date limite ?",),
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.PREVIOUS_PROCESSING,
                source_ref="candidate:scholarship",
            ),
        ),
        reasons=("Approfondir une inconnue factuelle",),
    )


def _result(findings):
    request = WebResearchRequest(
        mission=_mission(),
        mode=WebResearchMode.DEEPEN,
        requested_at=NOW,
    )
    source_a = WebResearchSource.from_locator(
        locator="https://example.edu/scholarship",
        observed_at=NOW,
        title="Official scholarship page",
    )
    source_b = WebResearchSource.from_locator(
        locator="https://example.edu/scholarship-rules",
        observed_at=NOW,
        title="Official scholarship rules",
    )
    candidate = WebResearchCandidate.build(
        request_ref=request.request_ref,
        label="Mechanical Engineering Scholarship",
        source_refs=(source_a.source_ref, source_b.source_ref),
        type_hints=("program",),
        summary="Scholarship candidate",
        attributes={EVIDENCE_FINDINGS_ATTRIBUTE: findings},
    )
    return WebResearchResult.from_request(
        request,
        started_at=NOW,
        completed_at=NOW,
        outcome=WebResearchOutcome.COMPLETED,
        stop_reason=WebResearchStopReason.COMPLETED,
        sources=(source_a, source_b),
        candidates=(candidate,),
    )


class EvidenceOutputTests(TestCase):
    def test_observed_fact_keeps_fact_level_source_provenance(self):
        result = _result(
            [
                {
                    "family": "REQUIREMENT",
                    "predicate": "application_deadline",
                    "state": "observed",
                    "value_text": "31 January 2027",
                    "source_refs": [],
                }
            ]
        )
        source_ref = result.sources[0].source_ref
        candidate = result.candidates[0]
        rows = [
            {
                "family": "REQUIREMENT",
                "predicate": "application_deadline",
                "state": "observed",
                "value_text": "31 January 2027",
                "source_refs": [source_ref],
            }
        ]
        result = _result(rows)
        output = EvidenceNormalizer().normalize(result)

        self.assertEqual(len(output.findings), 1)
        finding = output.findings[0]
        self.assertEqual(finding.state, EvidenceState.OBSERVED)
        self.assertEqual(finding.value_text, "31 January 2027")
        self.assertEqual(finding.source_refs, (result.sources[0].source_ref,))
        self.assertNotIn("artifact_ref", finding.to_payload())
        self.assertNotIn("artifact_observation_ref", finding.to_payload())

    def test_unknown_stays_unknown_instead_of_becoming_false(self):
        result = _result(
            [
                {
                    "family": "REQUIREMENT",
                    "predicate": "age_limit",
                    "state": "unknown",
                    "value_text": "",
                    "source_refs": [],
                }
            ]
        )
        output = EvidenceNormalizer().normalize(result)

        finding = output.findings[0]
        self.assertEqual(finding.state, EvidenceState.UNKNOWN)
        self.assertIsNone(finding.value_text)
        rendered = str(output.to_payload()).lower()
        self.assertNotIn("no_age_limit", rendered)
        self.assertNotIn("false", rendered)

    def test_distinct_supported_values_become_one_conflicting_finding(self):
        base = _result([])
        rows = [
            {
                "family": "REQUIREMENT",
                "predicate": "application_deadline",
                "state": "observed",
                "value_text": "31 January 2027",
                "source_refs": [base.sources[0].source_ref],
            },
            {
                "family": "REQUIREMENT",
                "predicate": "application_deadline",
                "state": "observed",
                "value_text": "15 February 2027",
                "source_refs": [base.sources[1].source_ref],
            },
        ]
        result = _result(rows)
        output = EvidenceNormalizer().normalize(result)

        finding = output.findings[0]
        self.assertEqual(finding.state, EvidenceState.CONFLICTING)
        self.assertEqual(len(finding.alternatives), 2)
        self.assertEqual(
            {item.value_text for item in finding.alternatives},
            {"31 January 2027", "15 February 2027"},
        )
        self.assertEqual(
            set(finding.support_source_refs),
            {item.source_ref for item in result.sources},
        )

    def test_not_applicable_requires_explicit_source_support(self):
        base = _result([])
        result = _result(
            [
                {
                    "family": "ECONOMIC",
                    "predicate": "application_fee",
                    "state": "not_applicable",
                    "value_text": "",
                    "source_refs": [base.sources[0].source_ref],
                }
            ]
        )
        output = EvidenceNormalizer().normalize(result)
        self.assertEqual(
            output.findings[0].state,
            EvidenceState.NOT_APPLICABLE,
        )

    def test_unknown_source_is_rejected_at_evidence_boundary(self):
        result = _result(
            [
                {
                    "family": "REQUIREMENT",
                    "predicate": "application_deadline",
                    "state": "observed",
                    "value_text": "31 January 2027",
                    "source_refs": ["web-research:source:v1:not-in-result"],
                }
            ]
        )
        output = EvidenceNormalizer().normalize(result)

        self.assertEqual(output.findings, ())
        self.assertIn(
            "evidence_finding_unknown_source",
            output.warning_codes,
        )

    def test_output_is_provider_neutral(self):
        result = _result(
            [
                {
                    "family": "REQUIREMENT",
                    "predicate": "age_limit",
                    "state": "unknown",
                    "value_text": "",
                    "source_refs": [],
                }
            ]
        )
        rendered = str(EvidenceNormalizer().normalize(result).to_payload()).lower()
        for forbidden in (
            "openai",
            "anthropic",
            "api_key",
            "authorization",
            "bearer ",
        ):
            self.assertNotIn(forbidden, rendered)
