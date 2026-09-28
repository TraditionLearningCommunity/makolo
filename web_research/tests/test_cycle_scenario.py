from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    CycleActionKind,
    CyclePlanner,
    DeepenPlanner,
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
    DiscoveryNormalizer,
    FreshnessPolicy,
    MinimalDiscoveryCoverage,
    STANDARD_ACTION_RESEARCH_SPECIFICATION,
    WatchChangeState,
    WatchFreshnessState,
    WatchLookup,
    WatchPlanner,
    WebResearchCandidate,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)


T0 = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


class _DiscoveryKnowledge:
    def __init__(self, state):
        self.state = state

    def lookup(self, **kwargs):
        if self.state is DiscoveryKnowledgeState.KNOWN:
            return DiscoveryLookup(
                state=self.state,
                known_refs=(
                    DiscoveryKnownRef("opportunity", "scholarship-1"),
                ),
                basis_codes=("scenario_known",),
            )
        return DiscoveryLookup(
            state=self.state,
            basis_codes=("scenario_not_yet_resolved",),
        )


class _WatchKnowledge:
    def __init__(self, lookup):
        self.lookup_value = lookup

    def assess(self, **kwargs):
        return self.lookup_value


class WebResearchCycleScenarioTests(SimpleTestCase):
    """Black-box deterministic scenario across the four standard outputs."""

    def _mission(self):
        return ResearchMission(
            primary_family=ResearchFamily.POSSIBILITY,
            subject="Bourses en génie mécanique",
            questions=(
                "Quelles bourses en génie mécanique existent dans le scope ?",
            ),
            origins=(
                ResearchOrigin(
                    kind=ResearchOriginKind.INITIAL,
                    source_ref="scenario:mechanical-engineering-scholarships",
                ),
            ),
            reasons=("Tester le cycle Web Research de bout en bout",),
            scope={"topic": "mechanical engineering scholarships"},
            limits={"max_candidates": 5, "max_queries": 3},
        )

    def _result(self, mission):
        request = WebResearchRequest(
            mission=mission,
            mode=WebResearchMode.DISCOVER,
            requested_at=T0,
        )
        source = WebResearchSource.from_locator(
            locator="https://example.edu/scholarships/mechanical-engineering",
            observed_at=T0,
            title="Mechanical Engineering Scholarship",
        )
        candidate = WebResearchCandidate.build(
            request_ref=request.request_ref,
            label="Mechanical Engineering Scholarship",
            source_refs=(source.source_ref,),
            type_hints=("scholarship",),
            summary="A sourced scholarship candidate used by the deterministic test.",
        )
        return WebResearchResult.from_request(
            request,
            started_at=T0,
            completed_at=T0,
            outcome=WebResearchOutcome.COMPLETED,
            stop_reason=WebResearchStopReason.COVERAGE_SATURATED,
            sources=(source,),
            candidates=(candidate,),
        )

    def _deepen(self, mission, discovery, now):
        return DeepenPlanner(MinimalDiscoveryCoverage()).plan(
            parent_mission=mission,
            discovery=discovery,
            specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
            generated_at=now,
        )

    def _watch(self, discovery, result, lookup, now):
        return WatchPlanner(_WatchKnowledge(lookup)).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=now,
        )

    def test_t0_empty_knowledge_discovers_and_requests_missing_dimensions(self):
        mission = self._mission()
        result = self._result(mission)
        discovery = DiscoveryNormalizer(
            _DiscoveryKnowledge(DiscoveryKnowledgeState.UNRESOLVED)
        ).normalize(result)
        deepen = self._deepen(mission, discovery, T0)
        watch = self._watch(
            discovery,
            result,
            WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=("source_not_known",),
            ),
            T0,
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=T0,
        )

        self.assertEqual(discovery.candidate_count, 1)
        self.assertEqual(
            discovery.records[0].knowledge_state,
            DiscoveryKnowledgeState.UNRESOLVED,
        )
        self.assertEqual(deepen.suggestion_count, 6)
        self.assertEqual(
            {item.family for item in deepen.suggestions},
            {
                ResearchFamily.REQUIREMENT,
                ResearchFamily.QUALIFICATION,
                ResearchFamily.ACTOR,
                ResearchFamily.SPATIOTEMPORAL,
                ResearchFamily.PROCEDURE,
                ResearchFamily.ECONOMIC,
            },
        )
        self.assertEqual(
            {item.action_kind for item in plan.actions},
            {
                CycleActionKind.DEEPEN_MISSION,
                CycleActionKind.OBSERVE_SOURCE,
            },
        )

    def test_t1_known_candidate_is_not_rediscovered_as_new(self):
        mission = self._mission()
        result = self._result(mission)
        discovery = DiscoveryNormalizer(
            _DiscoveryKnowledge(DiscoveryKnowledgeState.KNOWN)
        ).normalize(result)

        self.assertEqual(discovery.candidate_count, 1)
        self.assertEqual(
            discovery.records[0].knowledge_state,
            DiscoveryKnowledgeState.KNOWN,
        )
        self.assertEqual(
            discovery.records[0].known_refs[0].object_ref,
            "scholarship-1",
        )

    def test_t2_fresh_source_is_not_rechecked(self):
        mission = self._mission()
        result = self._result(mission)
        discovery = DiscoveryNormalizer(
            _DiscoveryKnowledge(DiscoveryKnowledgeState.KNOWN)
        ).normalize(result)
        now = T0 + timedelta(hours=2)
        watch = self._watch(
            discovery,
            result,
            WatchLookup(
                freshness_state=WatchFreshnessState.FRESH,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "scholarship-1",
                ),
                last_checked_at=T0,
                due_at=T0 + timedelta(days=1),
                last_change_state=WatchChangeState.UNCHANGED,
                basis_codes=("within_freshness_window",),
            ),
            now,
        )

        self.assertEqual(watch.due_source_refs, ())
        self.assertEqual(
            watch.targets[0].freshness_state,
            WatchFreshnessState.FRESH,
        )

    def test_t3_expired_source_is_selected_for_watch(self):
        mission = self._mission()
        result = self._result(mission)
        discovery = DiscoveryNormalizer(
            _DiscoveryKnowledge(DiscoveryKnowledgeState.KNOWN)
        ).normalize(result)
        now = T0 + timedelta(days=2)
        watch = self._watch(
            discovery,
            result,
            WatchLookup(
                freshness_state=WatchFreshnessState.DUE,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "scholarship-1",
                ),
                last_checked_at=T0,
                due_at=T0 + timedelta(days=1),
                last_change_state=WatchChangeState.UNCHANGED,
                basis_codes=("freshness_window_elapsed",),
            ),
            now,
        )

        self.assertEqual(
            watch.due_source_refs,
            (result.sources[0].source_ref,),
        )

    def test_standard_outputs_are_provider_neutral(self):
        mission = self._mission()
        result = self._result(mission)
        discovery = DiscoveryNormalizer(
            _DiscoveryKnowledge(DiscoveryKnowledgeState.UNRESOLVED)
        ).normalize(result)
        deepen = self._deepen(mission, discovery, T0)
        watch = self._watch(
            discovery,
            result,
            WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=("source_not_known",),
            ),
            T0,
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=T0,
        )

        rendered = str(
            {
                "research": result.to_payload(),
                "discovery": discovery.to_payload(),
                "deepen": deepen.to_payload(),
                "watch": watch.to_payload(),
                "plan": plan.to_payload(),
            }
        ).lower()
        for forbidden in (
            "openai",
            "anthropic",
            "api_key",
            "authorization",
            "bearer ",
        ):
            self.assertNotIn(forbidden, rendered)
