from datetime import datetime, timezone

from django.test import SimpleTestCase

from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    DeepenFamilySpec,
    DeepenPlanner,
    DeepenSpecification,
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
    DiscoveryNormalizer,
    FamilyCoverage,
    FamilyCoverageState,
    MinimalDiscoveryCoverage,
    STANDARD_ACTION_RESEARCH_SPECIFICATION,
    WebResearchCandidate,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)


NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def _mission():
    return ResearchMission(
        primary_family=ResearchFamily.POSSIBILITY,
        subject="Bourses de Master en génie mécanique",
        questions=("Quelles possibilités existent ?",),
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.INITIAL,
                source_ref="seed:scholarships",
            ),
        ),
        reasons=("Découvrir des possibilités",),
        priority=100,
        scope={"languages": ["fr", "en"]},
        limits={"max_queries": 5, "max_candidates": 20},
    )


def _discovery(parent, state=DiscoveryKnowledgeState.UNRESOLVED):
    request = WebResearchRequest(
        mission=parent,
        mode=WebResearchMode.DISCOVER,
        requested_at=NOW,
    )
    source = WebResearchSource.from_locator(
        locator="https://example.org/scholarship",
        observed_at=NOW,
        title="Scholarship",
    )
    candidate = WebResearchCandidate.build(
        request_ref=request.request_ref,
        label="Mechanical Engineering Scholarship",
        source_refs=(source.source_ref,),
        type_hints=("program",),
        summary="Scholarship candidate.",
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
    if state is DiscoveryKnowledgeState.KNOWN:
        known_refs = (
            DiscoveryKnownRef("opportunity", "known-1"),
        )
    lookup = DiscoveryLookup(
        state=state,
        known_refs=known_refs,
        basis_codes=("test_lookup",),
    )

    class StaticKnowledge:
        def lookup(self, **kwargs):
            return lookup

    return DiscoveryNormalizer(StaticKnowledge()).normalize(result)


class _Coverage:
    def __init__(self, mapping):
        self.mapping = mapping

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
                state=self.mapping.get(
                    spec.family,
                    FamilyCoverageState.MISSING,
                ),
                basis_codes=("test_coverage",),
            )
            for spec in specification.family_specs
        )


class DeepenPlanningTests(SimpleTestCase):
    def test_standard_action_specification_covers_all_eight_families(self):
        self.assertEqual(
            {item.family for item in STANDARD_ACTION_RESEARCH_SPECIFICATION.family_specs},
            set(ResearchFamily),
        )

    def test_minimal_discovery_coverage_only_claims_possibility_and_reference(self):
        parent = _mission()
        discovery = _discovery(parent)
        record = discovery.records[0]
        coverage = MinimalDiscoveryCoverage().assess(
            parent_mission=parent,
            discovery=discovery,
            record=record,
            specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
        )
        by_family = {item.family: item.state for item in coverage}

        self.assertEqual(
            by_family[ResearchFamily.POSSIBILITY],
            FamilyCoverageState.PRESENT,
        )
        self.assertEqual(
            by_family[ResearchFamily.REFERENCE],
            FamilyCoverageState.PRESENT,
        )
        self.assertEqual(
            by_family[ResearchFamily.REQUIREMENT],
            FamilyCoverageState.MISSING,
        )

    def test_planner_suggests_only_missing_partial_or_conflicting_families(self):
        parent = _mission()
        discovery = _discovery(parent)
        specification = DeepenSpecification(
            family_specs=(
                DeepenFamilySpec(
                    ResearchFamily.ACTOR,
                    ("Qui porte cette possibilité ?",),
                ),
                DeepenFamilySpec(
                    ResearchFamily.REQUIREMENT,
                    ("Quelles conditions sont demandées ?",),
                ),
                DeepenFamilySpec(
                    ResearchFamily.ECONOMIC,
                    ("Quels paramètres économiques s'appliquent ?",),
                ),
                DeepenFamilySpec(
                    ResearchFamily.REFERENCE,
                    ("Quelles références permettent de vérifier ?",),
                ),
            ),
        )
        planner = DeepenPlanner(
            _Coverage(
                {
                    ResearchFamily.ACTOR: FamilyCoverageState.PRESENT,
                    ResearchFamily.REQUIREMENT: FamilyCoverageState.MISSING,
                    ResearchFamily.ECONOMIC: FamilyCoverageState.PARTIAL,
                    ResearchFamily.REFERENCE: FamilyCoverageState.NOT_APPLICABLE,
                }
            )
        )
        output = planner.plan(
            parent_mission=parent,
            discovery=discovery,
            specification=specification,
            generated_at=NOW,
        )

        self.assertEqual(output.contract_version, 1)
        self.assertEqual(output.parent_mission_ref, parent.mission_ref)
        self.assertEqual(output.discovery_request_ref, discovery.request_ref)
        self.assertEqual(output.suggestion_count, 2)
        self.assertEqual(
            {item.family for item in output.suggestions},
            {
                ResearchFamily.REQUIREMENT,
                ResearchFamily.ECONOMIC,
            },
        )

    def test_suggestions_reuse_existing_research_mission_candidate_contract(self):
        parent = _mission()
        discovery = _discovery(parent)
        specification = DeepenSpecification(
            family_specs=(
                DeepenFamilySpec(
                    ResearchFamily.REQUIREMENT,
                    ("Quelles conditions sont demandées ?",),
                    unknowns=("conditions détaillées",),
                ),
            )
        )
        output = DeepenPlanner(
            _Coverage(
                {
                    ResearchFamily.REQUIREMENT: FamilyCoverageState.MISSING,
                }
            )
        ).plan(
            parent_mission=parent,
            discovery=discovery,
            specification=specification,
            generated_at=NOW,
        )

        suggestion = output.suggestions[0]
        mission = suggestion.mission_candidate.to_mission()
        record = discovery.records[0]

        self.assertEqual(
            mission.primary_family,
            ResearchFamily.REQUIREMENT,
        )
        self.assertEqual(mission.subject, record.label)
        self.assertEqual(mission.scope, parent.scope)
        self.assertEqual(mission.limits, parent.limits)
        self.assertEqual(mission.priority, parent.priority)
        self.assertEqual(
            mission.origins[0].kind,
            ResearchOriginKind.PREVIOUS_PROCESSING,
        )
        self.assertEqual(
            mission.origins[0].source_ref,
            record.candidate_ref,
        )
        self.assertEqual(
            mission.known_context["candidate_ref"],
            record.candidate_ref,
        )
        self.assertEqual(
            mission.known_context["source_refs"],
            record.source_refs,
        )

    def test_deepen_output_is_standard_and_provider_neutral(self):
        parent = _mission()
        discovery = _discovery(parent)
        output = DeepenPlanner(MinimalDiscoveryCoverage()).plan(
            parent_mission=parent,
            discovery=discovery,
            specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
            generated_at=NOW,
        )
        payload = output.to_payload()
        rendered = str(payload).lower()

        self.assertEqual(payload["contract_version"], 1)
        self.assertEqual(payload["target_count"], 1)
        self.assertEqual(payload["suggestion_count"], 6)
        self.assertNotIn("openai", rendered)
        self.assertNotIn("anthropic", rendered)
        self.assertNotIn("provider", rendered)
        self.assertNotIn("model", rendered)

    def test_planner_does_not_schedule_or_execute_suggested_missions(self):
        parent = _mission()
        discovery = _discovery(parent)
        output = DeepenPlanner(MinimalDiscoveryCoverage()).plan(
            parent_mission=parent,
            discovery=discovery,
            specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
            generated_at=NOW,
        )
        self.assertGreater(output.suggestion_count, 0)
        for suggestion in output.suggestions:
            self.assertTrue(suggestion.mission_ref.startswith("research-mission:v1:"))

    def test_known_candidate_can_still_have_missing_dimensions(self):
        parent = _mission()
        discovery = _discovery(
            parent,
            state=DiscoveryKnowledgeState.KNOWN,
        )
        output = DeepenPlanner(MinimalDiscoveryCoverage()).plan(
            parent_mission=parent,
            discovery=discovery,
            specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
            generated_at=NOW,
        )
        self.assertEqual(
            output.targets[0].knowledge_state,
            DiscoveryKnowledgeState.KNOWN.value,
        )
        self.assertGreater(output.suggestion_count, 0)

    def test_planner_rejects_discovery_from_another_parent_mission(self):
        parent = _mission()
        other = ResearchMission(
            primary_family=ResearchFamily.POSSIBILITY,
            subject="Autre sujet",
            questions=("Que trouve-t-on ?",),
            origins=(
                ResearchOrigin(
                    kind=ResearchOriginKind.INITIAL,
                    source_ref="seed:other",
                ),
            ),
            reasons=("Autre recherche",),
        )
        discovery = _discovery(other)
        with self.assertRaises(Exception):
            DeepenPlanner(MinimalDiscoveryCoverage()).plan(
                parent_mission=parent,
                discovery=discovery,
                specification=STANDARD_ACTION_RESEARCH_SPECIFICATION,
                generated_at=NOW,
            )
