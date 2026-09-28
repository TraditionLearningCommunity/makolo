from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    WebResearchCandidate,
    WebResearchContractError,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)


class WebResearchContractTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.mission = ResearchMission(
            primary_family=ResearchFamily.POSSIBILITY,
            subject="Bourses de Master en génie mécanique",
            questions=("Quelles possibilités existent ?",),
            origins=(
                ResearchOrigin(
                    kind=ResearchOriginKind.INITIAL,
                    source_ref="seed:mechanical-engineering-scholarships",
                ),
            ),
            reasons=("Construire la connaissance Makolo",),
            limits={"max_candidates": 50, "max_queries": 8},
        )
        self.request = WebResearchRequest(
            mission=self.mission,
            mode=WebResearchMode.DISCOVER,
            requested_at=self.now,
        )

    def test_request_reuses_research_mission_without_copying_business_truth(self):
        self.assertIs(self.request.mission, self.mission)
        self.assertEqual(self.request.mode, WebResearchMode.DISCOVER)
        self.assertEqual(
            self.request.to_payload()["mission"]["mission_ref"],
            self.mission.mission_ref,
        )
        self.assertNotIn("provider", self.request.to_payload())
        with self.assertRaises(FrozenInstanceError):
            self.request.mode = WebResearchMode.WATCH

    def test_request_ref_is_execution_specific_but_deterministic(self):
        same = WebResearchRequest(
            mission=self.mission,
            mode=WebResearchMode.DISCOVER,
            requested_at=self.now,
        )
        later = WebResearchRequest(
            mission=self.mission,
            mode=WebResearchMode.DISCOVER,
            requested_at=self.now + timedelta(seconds=1),
        )
        self.assertEqual(self.request.request_ref, same.request_ref)
        self.assertNotEqual(self.request.request_ref, later.request_ref)

    def test_request_requires_timezone_aware_execution_time(self):
        with self.assertRaises(WebResearchContractError):
            WebResearchRequest(
                mission=self.mission,
                mode=WebResearchMode.DISCOVER,
                requested_at=datetime(2026, 9, 28, 12, 0),
            )

    def test_source_is_a_web_citation_not_an_actor2_artifact(self):
        source = WebResearchSource.from_locator(
            locator="https://example.org/scholarship",
            observed_at=self.now,
            title="Scholarship",
        )
        names = {item.name for item in fields(WebResearchSource)}
        self.assertNotIn("artifact_ref", names)
        self.assertNotIn("artifact_observation_ref", names)
        self.assertEqual(source.locator, "https://example.org/scholarship")
        self.assertEqual(
            source.source_ref,
            WebResearchSource.from_locator(
                locator="https://example.org/scholarship",
                observed_at=self.now + timedelta(days=1),
            ).source_ref,
        )

    def test_source_rejects_non_web_or_credentialed_locator(self):
        for locator in (
            "file:///tmp/page.html",
            "mailto:test@example.org",
            "https://user:secret@example.org/page",
        ):
            with self.subTest(locator=locator):
                with self.assertRaises(WebResearchContractError):
                    WebResearchSource.from_locator(
                        locator=locator,
                        observed_at=self.now,
                    )

    def test_candidate_must_be_backed_by_at_least_one_source(self):
        with self.assertRaises(WebResearchContractError):
            WebResearchCandidate.build(
                request_ref=self.request.request_ref,
                label="Scholarship X",
                source_refs=(),
            )

    def test_result_rejects_candidate_with_unknown_source(self):
        candidate = WebResearchCandidate.build(
            request_ref=self.request.request_ref,
            label="Scholarship X",
            source_refs=("web-research:source:v1:missing",),
            type_hints=("program",),
        )
        with self.assertRaises(WebResearchContractError):
            WebResearchResult.from_request(
                self.request,
                started_at=self.now,
                completed_at=self.now + timedelta(seconds=2),
                outcome=WebResearchOutcome.COMPLETED,
                stop_reason=WebResearchStopReason.COMPLETED,
                candidates=(candidate,),
            )

    def test_sourced_discovery_result_is_provider_neutral(self):
        source = WebResearchSource.from_locator(
            locator="https://example.org/scholarship",
            observed_at=self.now,
            title="Official scholarship page",
        )
        candidate = WebResearchCandidate.build(
            request_ref=self.request.request_ref,
            label="Mechanical Engineering Scholarship",
            source_refs=(source.source_ref,),
            type_hints=("program",),
            summary="Master scholarship in mechanical engineering.",
            attributes={"language": "en"},
        )
        result = WebResearchResult.from_request(
            self.request,
            started_at=self.now,
            completed_at=self.now + timedelta(seconds=3),
            outcome=WebResearchOutcome.COMPLETED,
            stop_reason=WebResearchStopReason.COVERAGE_SATURATED,
            sources=(source,),
            candidates=(candidate,),
            engine_metadata={
                "provider_key": "provider-1",
                "model": "research-model",
            },
        )
        self.assertEqual(result.mission_ref, self.mission.mission_ref)
        self.assertEqual(result.candidates[0].source_refs, (source.source_ref,))
        self.assertNotIn("openai", str(result.to_payload()).lower())
        self.assertEqual(
            result.to_payload()["engine_metadata"]["provider_key"],
            "provider-1",
        )

    def test_engine_metadata_rejects_secret_material(self):
        with self.assertRaises(WebResearchContractError):
            WebResearchResult.from_request(
                self.request,
                started_at=self.now,
                completed_at=self.now + timedelta(seconds=1),
                outcome=WebResearchOutcome.NO_RESULTS,
                stop_reason=WebResearchStopReason.NO_NEW_CANDIDATES,
                engine_metadata={"api_key": "must-not-leak"},
            )

    def test_failed_result_requires_failure_code_and_no_candidates(self):
        with self.assertRaises(WebResearchContractError):
            WebResearchResult.from_request(
                self.request,
                started_at=self.now,
                completed_at=self.now,
                outcome=WebResearchOutcome.FAILED,
                stop_reason=WebResearchStopReason.FAILED,
            )

        failed = WebResearchResult.from_request(
            self.request,
            started_at=self.now,
            completed_at=self.now,
            outcome=WebResearchOutcome.FAILED,
            stop_reason=WebResearchStopReason.FAILED,
            failure_code="provider_unavailable",
        )
        self.assertEqual(failed.failure_code, "provider_unavailable")

    def test_no_results_does_not_mean_nothing_exists_on_the_web(self):
        result = WebResearchResult.from_request(
            self.request,
            started_at=self.now,
            completed_at=self.now + timedelta(seconds=1),
            outcome=WebResearchOutcome.NO_RESULTS,
            stop_reason=WebResearchStopReason.NO_NEW_CANDIDATES,
        )
        self.assertEqual(result.outcome, WebResearchOutcome.NO_RESULTS)
        self.assertEqual(
            result.stop_reason,
            WebResearchStopReason.NO_NEW_CANDIDATES,
        )
