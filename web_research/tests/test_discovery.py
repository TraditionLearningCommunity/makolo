from datetime import datetime, timezone

from django.test import SimpleTestCase, TestCase

from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunitySource,
    OpportunitySourceType,
)
from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
    DiscoveryNormalizer,
    WebResearchCandidate,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)
from web_research.django_discovery_catalog import (
    DjangoDiscoveryKnowledgeCatalog,
)


NOW = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)


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
    )


def _result(url="https://example.org/scholarship"):
    request = WebResearchRequest(
        mission=_mission(),
        mode=WebResearchMode.DISCOVER,
        requested_at=NOW,
    )
    source = WebResearchSource.from_locator(
        locator=url,
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
    return WebResearchResult.from_request(
        request,
        started_at=NOW,
        completed_at=NOW,
        outcome=WebResearchOutcome.COMPLETED,
        stop_reason=WebResearchStopReason.COVERAGE_SATURATED,
        sources=(source,),
        candidates=(candidate,),
    )


class _StaticKnowledge:
    def __init__(self, lookup):
        self.value = lookup

    def lookup(self, **kwargs):
        return self.value


class DiscoveryOutputContractTests(SimpleTestCase):
    def test_standard_output_is_provider_independent_and_versioned(self):
        result = _result()
        normalizer = DiscoveryNormalizer(
            _StaticKnowledge(
                DiscoveryLookup(
                    state=DiscoveryKnowledgeState.UNRESOLVED,
                    basis_codes=("catalog_coverage_incomplete",),
                )
            )
        )
        output = normalizer.normalize(result)
        payload = output.to_payload()

        self.assertEqual(payload["contract_version"], 1)
        self.assertEqual(payload["request_ref"], result.request_ref)
        self.assertEqual(payload["mission_ref"], result.mission_ref)
        self.assertEqual(payload["research_outcome"], "completed")
        self.assertEqual(payload["stop_reason"], "coverage_saturated")
        self.assertEqual(payload["source_count"], 1)
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(
            payload["counts_by_state"],
            {
                "known": 0,
                "not_known": 0,
                "ambiguous": 0,
                "unresolved": 1,
            },
        )
        self.assertNotIn("provider", payload)
        self.assertNotIn("model", payload)

    def test_known_output_requires_exactly_one_known_ref(self):
        normalizer = DiscoveryNormalizer(
            _StaticKnowledge(
                DiscoveryLookup(
                    state=DiscoveryKnowledgeState.KNOWN,
                    known_refs=(
                        DiscoveryKnownRef(
                            domain="opportunity",
                            object_ref="known-1",
                        ),
                    ),
                    basis_codes=("exact_known_source_url",),
                )
            )
        )
        output = normalizer.normalize(_result())
        record = output.records[0]
        self.assertEqual(
            record.knowledge_state,
            DiscoveryKnowledgeState.KNOWN,
        )
        self.assertEqual(record.known_refs[0].domain, "opportunity")

    def test_not_known_is_explicit_and_distinct_from_unresolved(self):
        not_known = DiscoveryNormalizer(
            _StaticKnowledge(
                DiscoveryLookup(
                    state=DiscoveryKnowledgeState.NOT_KNOWN,
                    basis_codes=("complete_catalog_miss",),
                )
            )
        ).normalize(_result())
        unresolved = DiscoveryNormalizer(
            _StaticKnowledge(
                DiscoveryLookup(
                    state=DiscoveryKnowledgeState.UNRESOLVED,
                    basis_codes=("catalog_coverage_incomplete",),
                )
            )
        ).normalize(_result())

        self.assertEqual(
            not_known.records[0].knowledge_state,
            DiscoveryKnowledgeState.NOT_KNOWN,
        )
        self.assertEqual(
            unresolved.records[0].knowledge_state,
            DiscoveryKnowledgeState.UNRESOLVED,
        )

    def test_ambiguous_requires_multiple_known_refs(self):
        lookup = DiscoveryLookup(
            state=DiscoveryKnowledgeState.AMBIGUOUS,
            known_refs=(
                DiscoveryKnownRef("opportunity", "a"),
                DiscoveryKnownRef("opportunity", "b"),
            ),
            basis_codes=("multiple_exact_matches",),
        )
        output = DiscoveryNormalizer(_StaticKnowledge(lookup)).normalize(
            _result()
        )
        self.assertEqual(
            output.records[0].knowledge_state,
            DiscoveryKnowledgeState.AMBIGUOUS,
        )
        self.assertEqual(len(output.records[0].known_refs), 2)


class DjangoDiscoveryKnowledgeCatalogTests(TestCase):
    def test_exact_opportunity_source_is_recognized_as_known(self):
        opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
        )
        OpportunitySource.objects.create(
            opportunity=opportunity,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official programme page",
            url="https://example.org/scholarship",
            is_primary=True,
        )

        output = DiscoveryNormalizer(
            DjangoDiscoveryKnowledgeCatalog()
        ).normalize(_result("https://example.org/scholarship"))

        record = output.records[0]
        self.assertEqual(
            record.knowledge_state,
            DiscoveryKnowledgeState.KNOWN,
        )
        self.assertEqual(
            record.known_refs,
            (
                DiscoveryKnownRef(
                    domain="opportunity",
                    object_ref=str(opportunity.pk),
                ),
            ),
        )
        self.assertIn("exact_known_source_url", record.basis_codes)

    def test_missing_exact_source_stays_unresolved_not_not_known(self):
        output = DiscoveryNormalizer(
            DjangoDiscoveryKnowledgeCatalog()
        ).normalize(_result("https://unknown.example/new-programme"))

        record = output.records[0]
        self.assertEqual(
            record.knowledge_state,
            DiscoveryKnowledgeState.UNRESOLVED,
        )
        self.assertIn("no_exact_known_source", record.basis_codes)
