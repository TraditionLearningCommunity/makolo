from datetime import datetime, timezone

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
    DeepenFamilySpec,
    DeepenPlanner,
    DeepenSpecification,
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
    DiscoveryNormalizer,
    FamilyCoverage,
    FamilyCoverageState,
    FreshnessPolicy,
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


NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


def _mission():
    return ResearchMission(
        primary_family=ResearchFamily.POSSIBILITY,
        subject="Possibilités génériques",
        questions=("Quelles possibilités existent ?",),
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.INITIAL,
                source_ref="seed:generic",
            ),
        ),
        reasons=("Découvrir puis approfondir",),
    )


def _material(knowledge_state):
    mission = _mission()
    request = WebResearchRequest(
        mission=mission,
        mode=WebResearchMode.DISCOVER,
        requested_at=NOW,
    )
    source = WebResearchSource.from_locator(
        locator="https://example.org/programme",
        observed_at=NOW,
        title="Programme",
    )
    candidate = WebResearchCandidate.build(
        request_ref=request.request_ref,
        label="Programme",
        source_refs=(source.source_ref,),
        type_hints=("program",),
        summary="Programme candidate.",
    )
    result = WebResearchResult.from_request(
        request,
        started_at=NOW,
        completed_at=NOW,
        outcome=WebResearchOutcome.COMPLETED,
        stop_reason=WebResearchStopReason.COVERAGE_SATURATED,
        sources=(source,),
        candidates=(candidate,),
    )

    known_refs = ()
    if knowledge_state is DiscoveryKnowledgeState.KNOWN:
        known_refs = (
            DiscoveryKnownRef("opportunity", "known-1"),
        )

    class Knowledge:
        def lookup(self, **kwargs):
            return DiscoveryLookup(
                state=knowledge_state,
                known_refs=known_refs,
                basis_codes=("test_knowledge",),
            )

    discovery = DiscoveryNormalizer(Knowledge()).normalize(result)
    return mission, result, discovery


class _Coverage:
    def __init__(self, state):
        self.state = state

    def assess(
        self,
        *,
        parent_mission,
        discovery,
        record,
        specification,
    ):
        return tuple(
            FamilyCoverage(
                family=spec.family,
                state=self.state,
                basis_codes=("test_coverage",),
            )
            for spec in specification.family_specs
        )


class _WatchKnowledge:
    def __init__(self, lookup):
        self.lookup_value = lookup

    def assess(self, **kwargs):
        return self.lookup_value


class CyclePlannerTests(SimpleTestCase):
    def _outputs(
        self,
        *,
        knowledge_state,
        coverage_state,
        watch_lookup,
    ):
        mission, result, discovery = _material(knowledge_state)
        specification = DeepenSpecification(
            family_specs=(
                DeepenFamilySpec(
                    ResearchFamily.REQUIREMENT,
                    ("Quelles conditions sont demandées ?",),
                ),
            )
        )
        deepen = DeepenPlanner(
            _Coverage(coverage_state)
        ).plan(
            parent_mission=mission,
            discovery=discovery,
            specification=specification,
            generated_at=NOW,
        )
        watch = WatchPlanner(
            _WatchKnowledge(watch_lookup)
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )
        return discovery, deepen, watch, result

    def test_missing_family_and_unknown_source_produce_deepen_and_observe(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.UNRESOLVED,
            coverage_state=FamilyCoverageState.MISSING,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=("source_not_known",),
            ),
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=NOW,
        )

        self.assertEqual(
            {item.action_kind for item in plan.actions},
            {
                CycleActionKind.DEEPEN_MISSION,
                CycleActionKind.OBSERVE_SOURCE,
            },
        )

    def test_due_known_source_produces_watch_action(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.KNOWN,
            coverage_state=FamilyCoverageState.PRESENT,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.DUE,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "known-1",
                ),
                due_at=NOW,
                basis_codes=("freshness_due",),
            ),
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=NOW,
        )
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(
            plan.actions[0].action_kind,
            CycleActionKind.WATCH_SOURCE,
        )

    def test_known_complete_and_fresh_produces_no_action(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.KNOWN,
            coverage_state=FamilyCoverageState.PRESENT,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.FRESH,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "known-1",
                ),
                last_checked_at=NOW,
                due_at=NOW.replace(day=29),
                basis_codes=("within_freshness_window",),
            ),
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=NOW,
        )
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(
            plan.actions[0].action_kind,
            CycleActionKind.NO_ACTION,
        )

    def test_unresolved_identity_without_deepen_is_held_for_resolution(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.UNRESOLVED,
            coverage_state=FamilyCoverageState.PRESENT,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=("source_not_known",),
            ),
        )
        plan = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=NOW,
        )
        kinds = [item.action_kind for item in plan.actions]
        self.assertIn(CycleActionKind.OBSERVE_SOURCE, kinds)
        self.assertIn(CycleActionKind.HOLD_FOR_RESOLUTION, kinds)

    def test_cycle_plan_is_standard_and_provider_neutral(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.KNOWN,
            coverage_state=FamilyCoverageState.PRESENT,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.FRESH,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "known-1",
                ),
                last_checked_at=NOW,
                due_at=NOW.replace(day=29),
                basis_codes=("within_freshness_window",),
            ),
        )
        payload = CyclePlanner().plan(
            discovery=discovery,
            deepen=deepen,
            watch=watch,
            generated_at=NOW,
        ).to_payload()
        rendered = str(payload).lower()

        self.assertEqual(payload["contract_version"], 1)
        self.assertEqual(payload["action_count"], 1)
        self.assertNotIn("openai", rendered)
        self.assertNotIn("anthropic", rendered)
        self.assertNotIn("provider", rendered)
        self.assertNotIn("model", rendered)

    def test_mismatched_outputs_are_rejected(self):
        discovery, deepen, watch, _result = self._outputs(
            knowledge_state=DiscoveryKnowledgeState.KNOWN,
            coverage_state=FamilyCoverageState.PRESENT,
            watch_lookup=WatchLookup(
                freshness_state=WatchFreshnessState.FRESH,
                known_ref=DiscoveryKnownRef(
                    "opportunity",
                    "known-1",
                ),
                last_checked_at=NOW,
                due_at=NOW.replace(day=29),
                basis_codes=("within_freshness_window",),
            ),
        )

        other_mission, other_result, other_discovery = _material(
            DiscoveryKnowledgeState.KNOWN
        )
        other_spec = DeepenSpecification(
            family_specs=(
                DeepenFamilySpec(
                    ResearchFamily.REQUIREMENT,
                    ("Conditions ?",),
                ),
            )
        )
        other_deepen = DeepenPlanner(
            _Coverage(FamilyCoverageState.PRESENT)
        ).plan(
            parent_mission=other_mission,
            discovery=other_discovery,
            specification=other_spec,
            generated_at=NOW,
        )

        # Same logical mission would yield the same ref, so force a distinct
        # discovery request by rebuilding it with a different execution time.
        other_request = WebResearchRequest(
            mission=other_mission,
            mode=WebResearchMode.DISCOVER,
            requested_at=NOW.replace(minute=1),
        )
        source = other_result.sources[0]
        candidate = WebResearchCandidate.build(
            request_ref=other_request.request_ref,
            label="Programme",
            source_refs=(source.source_ref,),
            type_hints=("program",),
            summary="Programme candidate.",
        )
        different_result = WebResearchResult.from_request(
            other_request,
            started_at=NOW,
            completed_at=NOW,
            outcome=WebResearchOutcome.COMPLETED,
            stop_reason=WebResearchStopReason.COVERAGE_SATURATED,
            sources=(source,),
            candidates=(candidate,),
        )

        class Knowledge:
            def lookup(self, **kwargs):
                return DiscoveryLookup(
                    state=DiscoveryKnowledgeState.KNOWN,
                    known_refs=(
                        DiscoveryKnownRef(
                            "opportunity",
                            "known-1",
                        ),
                    ),
                    basis_codes=("test",),
                )

        different_discovery = DiscoveryNormalizer(Knowledge()).normalize(
            different_result
        )
        different_deepen = DeepenPlanner(
            _Coverage(FamilyCoverageState.PRESENT)
        ).plan(
            parent_mission=other_mission,
            discovery=different_discovery,
            specification=other_spec,
            generated_at=NOW,
        )

        with self.assertRaises(Exception):
            CyclePlanner().plan(
                discovery=discovery,
                deepen=different_deepen,
                watch=watch,
                generated_at=NOW,
            )
