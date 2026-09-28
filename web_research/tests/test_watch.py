from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase, TestCase

from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunitySource,
    OpportunitySourceCheck,
    OpportunitySourceCheckResult,
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
    DiscoveryLookup,
    DiscoveryNormalizer,
    FreshnessPolicy,
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
from web_research.django_watch_catalog import DjangoWatchKnowledgeCatalog


NOW = datetime(2026, 9, 28, 15, 30, tzinfo=timezone.utc)


def _mission():
    return ResearchMission(
        primary_family=ResearchFamily.POSSIBILITY,
        subject="Possibilités à surveiller",
        questions=("Quelles possibilités existent ?",),
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.INITIAL,
                source_ref="seed:watch",
            ),
        ),
        reasons=("Construire puis maintenir la connaissance",),
    )


def _research_result(url="https://example.org/programme"):
    mission = _mission()
    request = WebResearchRequest(
        mission=mission,
        mode=WebResearchMode.DISCOVER,
        requested_at=NOW,
    )
    source = WebResearchSource.from_locator(
        locator=url,
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

    class Knowledge:
        def lookup(self, **kwargs):
            return DiscoveryLookup(
                state=DiscoveryKnowledgeState.UNRESOLVED,
                basis_codes=("test",),
            )

    discovery = DiscoveryNormalizer(Knowledge()).normalize(result)
    return result, discovery


class _StaticWatchKnowledge:
    def __init__(self, value):
        self.value = value

    def assess(self, **kwargs):
        return self.value


class WatchOutputContractTests(SimpleTestCase):
    def test_watch_output_is_standard_and_provider_neutral(self):
        result, discovery = _research_result()
        output = WatchPlanner(
            _StaticWatchKnowledge(
                WatchLookup(
                    freshness_state=WatchFreshnessState.UNRESOLVED,
                    basis_codes=("source_not_known",),
                )
            )
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )
        payload = output.to_payload()
        rendered = str(payload).lower()

        self.assertEqual(payload["contract_version"], 1)
        self.assertEqual(payload["target_count"], 1)
        self.assertEqual(
            payload["counts_by_state"],
            {"fresh": 0, "due": 0, "unresolved": 1},
        )
        self.assertEqual(payload["due_source_refs"], [])
        self.assertNotIn("openai", rendered)
        self.assertNotIn("provider", rendered)
        self.assertNotIn("model", rendered)

    def test_only_due_sources_are_selected_for_recheck(self):
        result, discovery = _research_result()
        output = WatchPlanner(
            _StaticWatchKnowledge(
                WatchLookup(
                    freshness_state=WatchFreshnessState.DUE,
                    known_ref=__import__(
                        "web_research"
                    ).DiscoveryKnownRef("opportunity", "known-1"),
                    due_at=NOW,
                    basis_codes=("known_source_never_checked",),
                )
            )
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=3600),
            generated_at=NOW,
        )

        self.assertEqual(
            output.due_source_refs,
            (result.sources[0].source_ref,),
        )

    def test_unresolved_source_is_not_scheduled_as_due(self):
        result, discovery = _research_result()
        output = WatchPlanner(
            _StaticWatchKnowledge(
                WatchLookup(
                    freshness_state=WatchFreshnessState.UNRESOLVED,
                    basis_codes=("source_not_known",),
                )
            )
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=3600),
            generated_at=NOW,
        )
        self.assertEqual(output.due_source_refs, ())


class DjangoWatchKnowledgeCatalogTests(TestCase):
    def _source(self, *, last_checked_at=None):
        opportunity = Opportunity.objects.create(
            kind=OpportunityKind.PROGRAM,
        )
        source = OpportunitySource.objects.create(
            opportunity=opportunity,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official programme",
            url="https://example.org/programme",
            is_primary=True,
        )
        if last_checked_at is not None:
            OpportunitySource.objects.filter(pk=source.pk).update(
                last_checked_at=last_checked_at
            )
            source.refresh_from_db()
        return source

    def test_known_source_never_checked_is_due(self):
        self._source()
        result, discovery = _research_result()

        output = WatchPlanner(
            DjangoWatchKnowledgeCatalog()
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )

        target = output.targets[0]
        self.assertEqual(
            target.freshness_state,
            WatchFreshnessState.DUE,
        )
        self.assertEqual(target.due_at, NOW)
        self.assertIn("known_source_never_checked", target.basis_codes)

    def test_recent_check_is_fresh(self):
        source = self._source(
            last_checked_at=NOW - timedelta(hours=2)
        )
        OpportunitySourceCheck.objects.create(
            source=source,
            result=OpportunitySourceCheckResult.UNCHANGED,
            checked_at=NOW - timedelta(hours=2),
            fingerprint="abc123",
        )
        result, discovery = _research_result()

        output = WatchPlanner(
            DjangoWatchKnowledgeCatalog()
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )

        target = output.targets[0]
        self.assertEqual(
            target.freshness_state,
            WatchFreshnessState.FRESH,
        )
        self.assertEqual(
            target.last_change_state,
            WatchChangeState.UNCHANGED,
        )
        self.assertEqual(
            target.due_at,
            NOW - timedelta(hours=2) + timedelta(days=1),
        )

    def test_old_check_is_due_without_deleting_history(self):
        source = self._source(
            last_checked_at=NOW - timedelta(days=3)
        )
        old = OpportunitySourceCheck.objects.create(
            source=source,
            result=OpportunitySourceCheckResult.CHANGED,
            checked_at=NOW - timedelta(days=3),
            fingerprint="old",
        )
        result, discovery = _research_result()

        output = WatchPlanner(
            DjangoWatchKnowledgeCatalog()
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )

        target = output.targets[0]
        self.assertEqual(
            target.freshness_state,
            WatchFreshnessState.DUE,
        )
        self.assertEqual(
            target.last_change_state,
            WatchChangeState.CHANGED,
        )
        self.assertTrue(
            OpportunitySourceCheck.objects.filter(pk=old.pk).exists()
        )

    def test_unknown_source_remains_unresolved(self):
        result, discovery = _research_result(
            "https://unknown.example/new"
        )
        output = WatchPlanner(
            DjangoWatchKnowledgeCatalog()
        ).plan(
            discovery=discovery,
            sources=result.sources,
            policy=FreshnessPolicy(max_age_seconds=86400),
            generated_at=NOW,
        )
        self.assertEqual(
            output.targets[0].freshness_state,
            WatchFreshnessState.UNRESOLVED,
        )
        self.assertEqual(output.due_source_refs, ())
