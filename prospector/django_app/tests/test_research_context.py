from datetime import datetime, timedelta, timezone

from django.test import TestCase

from prospector.contracts import (
    ProspectingCandidate,
    ProspectingEvidence,
)
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_research_context import (
    DjangoProspectorResearchContextSource,
)
from research_missions.contracts import (
    ResearchFamily,
    ResearchMissionCandidate,
    ResearchOrigin,
    ResearchOriginKind,
)
from research_missions.ports import ResearchContextSourcePort
from research_missions.prospecting import (
    ProspectingPlan,
    project_to_prospecting_mission,
)


class DjangoProspectorResearchContextSourceTests(TestCase):
    def setUp(self):
        self.frontier = DjangoFrontierStore()
        self.source = DjangoProspectorResearchContextSource()
        self.now = datetime(
            2026,
            9,
            24,
            10,
            0,
            tzinfo=timezone.utc,
        )
        self.plan = ProspectingPlan(
            host_tlds=("org",),
            path_terms=("scholarship",),
        )

    def _admit(
        self,
        *,
        locator,
        research_candidate,
        discovered_at=None,
    ):
        discovered_at = discovered_at or self.now
        mission = research_candidate.to_mission()
        prospecting = project_to_prospecting_mission(
            mission,
            self.plan,
            issued_at=discovered_at,
        )
        return self.frontier.admit_sync(
            ProspectingCandidate(
                locator=locator,
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=discovered_at,
                        provider="test-index",
                    ),
                ),
                policy_context={
                    "mission_key": prospecting.mission_key,
                    "mission_fingerprint": prospecting.fingerprint,
                    "source_name": "test-index",
                    "mission_context": dict(prospecting.context),
                },
            )
        )

    def _candidate(self, *, source_ref, reason):
        return ResearchMissionCandidate(
            primary_family=ResearchFamily.QUALIFICATION,
            subject="TOEFL",
            questions=(
                "Qu'est-ce qui constitue une preuve valide ?",
            ),
            origin=ResearchOrigin(
                kind=ResearchOriginKind.REQUIREMENT,
                source_ref=source_ref,
            ),
            reason=reason,
            known_context={"issuer": "ETS"},
            unknowns=("validity",),
            scope={"purpose": "scholarship"},
        )

    def test_read_model_implements_read_only_port(self):
        self.assertIsInstance(
            self.source,
            ResearchContextSourcePort,
        )

    def test_target_lookup_returns_corresponding_research_context(self):
        target = self._admit(
            locator="https://example.test/toefl",
            research_candidate=self._candidate(
                source_ref="requirement:scholarship-a:toefl",
                reason="Bourse A exige TOEFL",
            ),
        )

        contexts = self.source.contexts_for_target(
            target.target_key
        )

        self.assertEqual(len(contexts), 1)
        context = contexts[0]
        self.assertEqual(
            context.primary_family,
            ResearchFamily.QUALIFICATION,
        )
        self.assertEqual(context.subject, "TOEFL")
        self.assertEqual(
            context.questions,
            ("Qu'est-ce qui constitue une preuve valide ?",),
        )
        self.assertEqual(
            context.known_context["issuer"],
            "ETS",
        )
        self.assertEqual(
            context.origins[0].source_ref,
            "requirement:scholarship-a:toefl",
        )

    def test_same_need_merges_distinct_provenance_for_same_target(self):
        first = self._candidate(
            source_ref="requirement:scholarship-a:toefl",
            reason="Bourse A exige TOEFL",
        )
        second = self._candidate(
            source_ref="requirement:scholarship-b:toefl",
            reason="Bourse B exige TOEFL",
        )
        self.assertEqual(first.mission_ref, second.mission_ref)

        target = self._admit(
            locator="https://example.test/toefl",
            research_candidate=first,
        )
        self._admit(
            locator="https://example.test/toefl#same-target",
            research_candidate=second,
            discovered_at=self.now + timedelta(minutes=1),
        )

        contexts = self.source.contexts_for_target(
            target.target_key
        )

        self.assertEqual(len(contexts), 1)
        self.assertEqual(
            contexts[0].mission_ref,
            first.mission_ref,
        )
        self.assertEqual(
            {origin.source_ref for origin in contexts[0].origins},
            {
                "requirement:scholarship-a:toefl",
                "requirement:scholarship-b:toefl",
            },
        )
        self.assertEqual(
            set(contexts[0].reasons),
            {
                "Bourse A exige TOEFL",
                "Bourse B exige TOEFL",
            },
        )

    def test_lookup_is_isolated_by_target_key(self):
        target_a = self._admit(
            locator="https://example.test/toefl",
            research_candidate=self._candidate(
                source_ref="requirement:scholarship-a:toefl",
                reason="Bourse A exige TOEFL",
            ),
        )
        other = ResearchMissionCandidate(
            primary_family=ResearchFamily.ECONOMIC,
            subject="Bourse X",
            questions=("Quel est le montant ?",),
            origin=ResearchOrigin(
                kind=ResearchOriginKind.CANONICAL_REALITY,
                source_ref="reality:scholarship-x",
            ),
            reason="Montant inconnu",
        )
        self._admit(
            locator="https://example.test/scholarship-x/cost",
            research_candidate=other,
        )

        contexts = self.source.contexts_for_target(
            target_a.target_key
        )

        self.assertEqual(len(contexts), 1)
        self.assertEqual(
            contexts[0].primary_family,
            ResearchFamily.QUALIFICATION,
        )
        self.assertNotEqual(
            contexts[0].mission_ref,
            other.mission_ref,
        )

    def test_lookup_without_research_provenance_returns_empty_tuple(self):
        target = self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://example.test/plain",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="manual_test",
                        discovered_at=self.now,
                    ),
                ),
                policy_context={"campaign_key": "legacy"},
            )
        )

        self.assertEqual(
            self.source.contexts_for_target(target.target_key),
            (),
        )
