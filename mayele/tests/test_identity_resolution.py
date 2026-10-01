from datetime import datetime, timezone
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.cognition import (
    CandidateStatus,
    Interpretation,
    InterpretationMode,
    InterpretationReferent,
    RealityCandidate,
    ReferentKind,
    RelationCandidate,
    RelationCandidateParticipant,
)
from mayele.identity import (
    IdentityResolution,
    IdentityResolutionBasis,
    IdentityResolutionBasisKind,
    IdentityResolutionStatus,
    validate_identity_resolution,
)
from mayele.knowledge import (
    Condition,
    KnowledgeSupport,
    Property,
    Proposition,
    PropositionAssessment,
    Reality,
    Relation,
)
from mayele.observation import (
    Mention,
    Observation,
    ObservationAttempt,
    ObservationAttemptOutcome,
    ObservedArtifact,
    ObservedStatement,
    Passage,
    Source,
    SourceKind,
)


class IdentityResolutionTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.source = Source(
            "source:catalogue",
            SourceKind.WEB_PAGE,
            locator="https://example.invalid/catalogue",
        )
        attempt = ObservationAttempt(
            "attempt:1", self.source, self.now, ObservationAttemptOutcome.SUCCESS
        )
        observation = Observation("observation:1", attempt, self.now)
        artifact = ObservedArtifact("artifact:1", observation, "text/plain")
        passage = Passage("passage:1", artifact, "line=1")
        self.statement = ObservedStatement(
            "statement:1",
            passage,
            "UNILU and University of Lubumbashi are referenced here.",
        )
        self.unilu = self._mention("mention:unilu", "UNILU")
        self.full_name = self._mention(
            "mention:university-lubumbashi", "University of Lubumbashi"
        )
        self.interpretation = Interpretation(
            "interpretation:1",
            self.statement,
            self.now,
            InterpretationMode.EXPLICIT,
            mentions=(self.unilu, self.full_name),
        )
        self.unilu_ref = InterpretationReferent(
            ReferentKind.MENTION, self.unilu.mention_ref
        )
        self.full_ref = InterpretationReferent(
            ReferentKind.MENTION, self.full_name.mention_ref
        )
        self.candidate = RealityCandidate(
            "candidate:unilu",
            self.interpretation,
            source_referent=self.unilu_ref,
            label="UNILU",
        )
        self.reality = Reality("reality:unilu", "Université de Lubumbashi")

    def _mention(self, ref: str, surface: str) -> Mention:
        start = self.statement.text.index(surface)
        return Mention(ref, self.statement, surface, start=start, end=start + len(surface))

    def _mention_basis(self, mention: Mention):
        return (
            IdentityResolutionBasis(
                IdentityResolutionBasisKind.MENTION, mention.mention_ref
            ),
            IdentityResolutionBasis(
                IdentityResolutionBasisKind.OBSERVED_STATEMENT,
                mention.statement.statement_ref,
            ),
        )

    def _candidate_basis(self, candidate: RealityCandidate):
        return (
            IdentityResolutionBasis(
                IdentityResolutionBasisKind.REALITY_CANDIDATE,
                candidate.candidate_ref,
            ),
            IdentityResolutionBasis(
                IdentityResolutionBasisKind.INTERPRETATION,
                candidate.interpretation.interpretation_ref,
            ),
        )

    def _for_mention(
        self,
        ref: str,
        mention: Mention,
        status: IdentityResolutionStatus,
        *,
        reality=None,
        alternatives=(),
        supersedes=None,
        scope=None,
        basis=None,
    ) -> IdentityResolution:
        return IdentityResolution(
            ref,
            InterpretationReferent(ReferentKind.MENTION, mention.mention_ref),
            mention.scope,
            self.now,
            status,
            reality=reality,
            alternatives=alternatives,
            basis=basis or self._mention_basis(mention),
            supersedes_resolution_ref=supersedes,
            scope=scope,
        )

    def _for_candidate(
        self,
        ref: str,
        candidate: RealityCandidate,
        status: IdentityResolutionStatus,
        *,
        reality=None,
    ) -> IdentityResolution:
        return IdentityResolution(
            ref,
            InterpretationReferent(
                ReferentKind.REALITY_CANDIDATE, candidate.candidate_ref
            ),
            candidate.scope,
            self.now,
            status,
            reality=reality,
            basis=self._candidate_basis(candidate),
        )

    def _private_mention(self, suffix: str, surface: str) -> Mention:
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        source = Source(
            f"source:private:{suffix}", SourceKind.CONNECTED_FILE, scope=private
        )
        attempt = ObservationAttempt(
            f"attempt:private:{suffix}",
            source,
            self.now,
            ObservationAttemptOutcome.SUCCESS,
        )
        observation = Observation(f"observation:private:{suffix}", attempt, self.now)
        artifact = ObservedArtifact(
            f"artifact:private:{suffix}", observation, "text/plain"
        )
        statement = ObservedStatement(
            f"statement:private:{suffix}",
            Passage(f"passage:private:{suffix}", artifact, "line=1"),
            surface,
        )
        return Mention(
            f"mention:private:{suffix}",
            statement,
            surface,
            start=0,
            end=len(surface),
        )

    def test_statuses_are_explicit(self):
        self.assertEqual(
            set(IdentityResolutionStatus),
            {
                IdentityResolutionStatus.RESOLVED,
                IdentityResolutionStatus.PROVISIONAL,
                IdentityResolutionStatus.UNRESOLVED,
            },
        )

    def test_mention_and_candidate_can_remain_unresolved(self):
        mention_resolution = self._for_mention(
            "resolution:mention", self.unilu, IdentityResolutionStatus.UNRESOLVED
        )
        candidate_resolution = self._for_candidate(
            "resolution:candidate", self.candidate, IdentityResolutionStatus.UNRESOLVED
        )
        self.assertIsNone(
            validate_identity_resolution(mention_resolution, self.unilu).reality
        )
        self.assertIsNone(
            validate_identity_resolution(candidate_resolution, self.candidate).reality
        )

    def test_resolved_and_provisional_require_selected_reality(self):
        for status in (
            IdentityResolutionStatus.RESOLVED,
            IdentityResolutionStatus.PROVISIONAL,
        ):
            with self.subTest(status=status), self.assertRaises(MayeleContractError):
                self._for_mention("resolution:missing", self.unilu, status)
        provisional = self._for_mention(
            "resolution:provisional",
            self.unilu,
            IdentityResolutionStatus.PROVISIONAL,
            reality=self.reality,
        )
        self.assertIs(provisional.status, IdentityResolutionStatus.PROVISIONAL)

    def test_unresolved_never_selects_reality_but_can_keep_alternatives(self):
        with self.assertRaises(MayeleContractError):
            self._for_mention(
                "resolution:bad-unresolved",
                self.unilu,
                IdentityResolutionStatus.UNRESOLVED,
                reality=self.reality,
            )
        resolution = self._for_mention(
            "resolution:ambiguous",
            self.unilu,
            IdentityResolutionStatus.UNRESOLVED,
            alternatives=(Reality("reality:a"), Reality("reality:b")),
        )
        self.assertIsNone(resolution.reality)
        self.assertEqual(len(resolution.alternatives), 2)

    def test_multiple_referents_can_resolve_to_same_reality_without_merging(self):
        second = RealityCandidate(
            "candidate:unilu-full",
            self.interpretation,
            source_referent=self.full_ref,
            label="University of Lubumbashi",
        )
        first_resolution = self._for_candidate(
            "resolution:candidate:short",
            self.candidate,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        second_resolution = self._for_candidate(
            "resolution:candidate:full",
            second,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        validate_identity_resolution(first_resolution, self.candidate)
        validate_identity_resolution(second_resolution, second)
        self.assertNotEqual(self.candidate.candidate_ref, second.candidate_ref)
        self.assertEqual(
            first_resolution.reality.reality_ref,
            second_resolution.reality.reality_ref,
        )

    def test_homonyms_stay_distinct_and_aliases_can_converge(self):
        candidate_a = RealityCandidate(
            "candidate:homonym:a", self.interpretation, label="University X"
        )
        candidate_b = RealityCandidate(
            "candidate:homonym:b", self.interpretation, label="University X"
        )
        self.assertEqual(candidate_a.label, candidate_b.label)
        self.assertNotEqual(
            Reality("reality:homonym:a").reality_ref,
            Reality("reality:homonym:b").reality_ref,
        )
        short = self._for_mention(
            "resolution:alias:short",
            self.unilu,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        full = self._for_mention(
            "resolution:alias:full",
            self.full_name,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        self.assertNotEqual(self.unilu.surface, self.full_name.surface)
        self.assertEqual(short.reality.reality_ref, full.reality.reality_ref)

    def test_candidate_fingerprint_and_source_locator_do_not_decide_identity(self):
        clone = RealityCandidate(
            "candidate:clone",
            self.interpretation,
            source_referent=self.unilu_ref,
            label="UNILU",
        )
        self.assertEqual(self.candidate.fingerprint, clone.fingerprint)
        self.assertIsNone(
            self._for_candidate(
                "resolution:fingerprint",
                clone,
                IdentityResolutionStatus.UNRESOLVED,
            ).reality
        )
        other = RealityCandidate("candidate:other", self.interpretation, label="Other")
        self.assertEqual(
            clone.interpretation.statement.passage.artifact.observation.source.locator,
            other.interpretation.statement.passage.artifact.observation.source.locator,
        )
        self.assertNotEqual(clone.candidate_ref, other.candidate_ref)

    def test_rejected_candidate_cannot_be_promoted(self):
        rejected = RealityCandidate(
            "candidate:rejected",
            self.interpretation,
            label="Rejected",
            status=CandidateStatus.REJECTED,
        )
        resolution = self._for_candidate(
            "resolution:rejected",
            rejected,
            IdentityResolutionStatus.RESOLVED,
            reality=Reality("reality:rejected-test"),
        )
        with self.assertRaises(MayeleContractError):
            validate_identity_resolution(resolution, rejected)

    def test_resolution_keeps_identity_basis_separate_from_knowledge_support(self):
        resolution = self._for_mention(
            "resolution:lineage",
            self.unilu,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        self.assertEqual(resolution.basis[0].ref, self.unilu.mention_ref)
        self.assertNotIsInstance(resolution.basis[0], KnowledgeSupport)

    def test_resolved_at_must_be_timezone_aware(self):
        with self.assertRaises(MayeleContractError):
            IdentityResolution(
                "resolution:naive",
                self.unilu_ref,
                self.unilu.scope,
                datetime(2026, 10, 1, 12, 0, 0),
                IdentityResolutionStatus.UNRESOLVED,
                basis=self._mention_basis(self.unilu),
            )

    def test_scope_cannot_widen_and_public_reality_does_not_publish_private_basis(self):
        mention = self._private_mention("one", "Public University")
        with self.assertRaises(MayeleContractError):
            self._for_mention(
                "resolution:widen",
                mention,
                IdentityResolutionStatus.UNRESOLVED,
                scope=KnowledgeScope(ScopeVisibility.PUBLIC),
            )
        resolution = self._for_mention(
            "resolution:private",
            mention,
            IdentityResolutionStatus.RESOLVED,
            reality=Reality("reality:public-university", "Public University"),
        )
        validate_identity_resolution(resolution, mention)
        self.assertIs(resolution.scope.visibility, ScopeVisibility.PRIVATE)
        self.assertFalse(hasattr(resolution.reality, "scope"))

    def test_resolution_is_revisable_without_rewriting_history(self):
        first = self._for_mention(
            "resolution:t1",
            self.unilu,
            IdentityResolutionStatus.PROVISIONAL,
            reality=Reality("reality:tentative-a"),
        )
        second = self._for_mention(
            "resolution:t2",
            self.unilu,
            IdentityResolutionStatus.RESOLVED,
            reality=Reality("reality:corrected-b"),
            supersedes=first.resolution_ref,
        )
        self.assertEqual(second.supersedes_resolution_ref, first.resolution_ref)
        self.assertIs(first.status, IdentityResolutionStatus.PROVISIONAL)
        self.assertEqual(first.reality.reality_ref, "reality:tentative-a")
        self.assertEqual(second.reality.reality_ref, "reality:corrected-b")

    def test_supersession_method_and_alternatives_are_structurally_guarded(self):
        with self.assertRaises(MayeleContractError):
            self._for_mention(
                "resolution:self",
                self.unilu,
                IdentityResolutionStatus.UNRESOLVED,
                supersedes="resolution:self",
            )
        with self.assertRaises(MayeleContractError):
            IdentityResolution(
                "resolution:method",
                self.unilu_ref,
                self.unilu.scope,
                self.now,
                IdentityResolutionStatus.UNRESOLVED,
                basis=self._mention_basis(self.unilu),
                method_version="1",
            )
        duplicate = Reality("reality:alternative")
        with self.assertRaises(MayeleContractError):
            self._for_mention(
                "resolution:duplicate-alternatives",
                self.unilu,
                IdentityResolutionStatus.UNRESOLVED,
                alternatives=(duplicate, duplicate),
            )
        with self.assertRaises(MayeleContractError):
            self._for_mention(
                "resolution:selected-alternative",
                self.unilu,
                IdentityResolutionStatus.RESOLVED,
                reality=self.reality,
                alternatives=(self.reality,),
            )

    def test_gate_preserves_subject_lineage_and_rejects_reality_referent(self):
        missing = self._for_mention(
            "resolution:missing-basis",
            self.unilu,
            IdentityResolutionStatus.UNRESOLVED,
            basis=(
                IdentityResolutionBasis(
                    IdentityResolutionBasisKind.OBSERVED_STATEMENT,
                    self.statement.statement_ref,
                ),
            ),
        )
        with self.assertRaises(MayeleContractError):
            validate_identity_resolution(missing, self.unilu)
        redundant = IdentityResolution(
            "resolution:reality-referent",
            InterpretationReferent(ReferentKind.REALITY, self.reality.reality_ref),
            KnowledgeScope(),
            self.now,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
            basis=(
                IdentityResolutionBasis(
                    IdentityResolutionBasisKind.REALITY, self.reality.reality_ref
                ),
            ),
        )
        with self.assertRaises(MayeleContractError):
            validate_identity_resolution(redundant, self.unilu)

    def test_n_ary_relation_participants_can_resolve_independently(self):
        relation = RelationCandidate(
            "candidate:relation",
            self.interpretation,
            "CONNECTS",
            (
                RelationCandidateParticipant("a", self.unilu_ref),
                RelationCandidateParticipant("b", self.full_ref),
                RelationCandidateParticipant(
                    "c",
                    InterpretationReferent(
                        ReferentKind.REALITY_CANDIDATE, "candidate:third"
                    ),
                ),
            ),
        )
        self.assertEqual(len(relation.participants), 3)
        resolved = self._for_mention(
            "resolution:participant:a",
            self.unilu,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        unresolved = self._for_mention(
            "resolution:participant:b",
            self.full_name,
            IdentityResolutionStatus.UNRESOLVED,
        )
        self.assertIsNotNone(resolved.reality)
        self.assertIsNone(unresolved.reality)

    def test_identity_resolution_builds_no_world_structure_or_epistemic_assessment(self):
        resolution = self._for_mention(
            "resolution:boundary",
            self.unilu,
            IdentityResolutionStatus.RESOLVED,
            reality=self.reality,
        )
        for forbidden in (
            Property,
            Relation,
            Condition,
            Proposition,
            KnowledgeSupport,
            PropositionAssessment,
        ):
            self.assertNotIsInstance(resolution, forbidden)
        self.assertFalse(hasattr(resolution, "proposition"))
        self.assertFalse(hasattr(resolution, "assessment"))
        self.assertFalse(hasattr(resolution, "knowledge_completeness"))
