from datetime import datetime, timezone
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.cognition import (
    CandidateStatus,
    ConditionCandidate,
    Interpretation,
    InterpretationMode,
    InterpretationReferent,
    PropertyCandidate,
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
)
from mayele.knowledge import (
    KnowledgeSupport,
    KnowledgeSupportTrace,
    KnowledgeValue,
    Proposition,
    PropositionAssessment,
    PropositionConstruction,
    PropositionKind,
    Reality,
    SupportDisposition,
    TemporalValidity,
    build_knowledge_support,
    build_proposition_construction,
)
from mayele.knowledge.gate import (
    validate_knowledge_support_lineage,
    validate_proposition_construction,
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


class PropositionSupportLineageTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.source = Source(
            "source:a",
            SourceKind.WEB_PAGE,
            locator="https://example.invalid/a",
        )
        self.statement = self._statement(
            self.source,
            "one",
            "University X offers Scholarship Y. Application fee: 50 USD.",
        )
        self.university = self._mention("mention:university", "University X")
        self.scholarship = self._mention("mention:scholarship", "Scholarship Y")
        self.interpretation = Interpretation(
            "interpretation:1",
            self.statement,
            self.now,
            InterpretationMode.EXPLICIT,
            mentions=(self.university, self.scholarship),
        )
        self.university_ref = InterpretationReferent(
            ReferentKind.MENTION, self.university.mention_ref
        )
        self.scholarship_ref = InterpretationReferent(
            ReferentKind.MENTION, self.scholarship.mention_ref
        )
        self.reality_university = Reality("reality:university-x", "University X")
        self.reality_scholarship = Reality("reality:scholarship-y", "Scholarship Y")

    def _statement(self, source, suffix, text):
        attempt = ObservationAttempt(
            f"attempt:{suffix}",
            source,
            self.now,
            ObservationAttemptOutcome.SUCCESS,
        )
        observation = Observation(f"observation:{suffix}", attempt, self.now)
        artifact = ObservedArtifact(
            f"artifact:{suffix}",
            observation,
            "text/plain",
        )
        return ObservedStatement(
            f"statement:{suffix}",
            Passage(f"passage:{suffix}", artifact, "line=1"),
            text,
        )

    def _mention(self, ref, surface):
        start = self.statement.text.index(surface)
        return Mention(
            ref,
            self.statement,
            surface,
            start=start,
            end=start + len(surface),
        )

    def _resolution(
        self,
        ref,
        referent,
        status,
        reality=None,
        *,
        scope=None,
    ):
        kind = {
            ReferentKind.MENTION: IdentityResolutionBasisKind.MENTION,
            ReferentKind.REALITY_CANDIDATE: IdentityResolutionBasisKind.REALITY_CANDIDATE,
        }[referent.kind]
        referent_scope = scope or self.interpretation.scope
        return IdentityResolution(
            ref,
            referent,
            referent_scope,
            self.now,
            status,
            reality=reality,
            basis=(IdentityResolutionBasis(kind, referent.ref),),
            scope=scope,
        )

    def test_reality_candidate_resolved_builds_reality_exists(self):
        candidate = RealityCandidate("candidate:reality", self.interpretation, label="University X")
        referent = InterpretationReferent(ReferentKind.REALITY_CANDIDATE, candidate.candidate_ref)
        resolution = self._resolution(
            "resolution:reality", referent, IdentityResolutionStatus.RESOLVED, self.reality_university
        )
        construction = build_proposition_construction(
            candidate, self.now, identity_resolutions=(resolution,)
        )
        self.assertIs(construction.proposition.kind, PropositionKind.REALITY_EXISTS)
        self.assertEqual(
            construction.proposition.target.reality_ref,
            self.reality_university.reality_ref,
        )
        self.assertIs(
            validate_proposition_construction(construction, candidate),
            construction.proposition,
        )

    def test_reality_candidate_unresolved_never_fabricates_reality(self):
        candidate = RealityCandidate("candidate:unresolved", self.interpretation)
        referent = InterpretationReferent(ReferentKind.REALITY_CANDIDATE, candidate.candidate_ref)
        resolution = self._resolution(
            "resolution:unresolved", referent, IdentityResolutionStatus.UNRESOLVED
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, self.now, identity_resolutions=(resolution,)
            )

    def test_rejected_candidate_is_not_promoted(self):
        candidate = RealityCandidate(
            "candidate:rejected",
            self.interpretation,
            status=CandidateStatus.REJECTED,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(candidate, self.now)

    def test_property_with_direct_reality_needs_no_resolution(self):
        candidate = PropertyCandidate(
            "candidate:property:direct",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, self.reality_university.reality_ref),
            "application_fee",
            "50 USD",
        )
        construction = build_proposition_construction(candidate, self.now)
        self.assertIs(construction.proposition.kind, PropositionKind.PROPERTY_HOLDS)
        self.assertEqual(construction.identity_resolutions, ())
        self.assertEqual(
            construction.proposition.target.reality_ref,
            self.reality_university.reality_ref,
        )

    def test_property_mention_requires_resolution(self):
        candidate = PropertyCandidate(
            "candidate:property:mention",
            self.interpretation,
            self.university_ref,
            "application_fee",
            "50 USD",
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(candidate, self.now)

    def test_property_unresolved_is_refused(self):
        candidate = PropertyCandidate(
            "candidate:property:unresolved",
            self.interpretation,
            self.university_ref,
            "application_fee",
            "50 USD",
        )
        unresolved = self._resolution(
            "resolution:property:unresolved",
            self.university_ref,
            IdentityResolutionStatus.UNRESOLVED,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, self.now, identity_resolutions=(unresolved,)
            )

    def test_property_provisional_is_kept_explicitly(self):
        candidate = PropertyCandidate(
            "candidate:property:provisional",
            self.interpretation,
            self.university_ref,
            "application_fee",
            "50 USD",
        )
        provisional = self._resolution(
            "resolution:property:provisional",
            self.university_ref,
            IdentityResolutionStatus.PROVISIONAL,
            self.reality_university,
        )
        construction = build_proposition_construction(
            candidate, self.now, identity_resolutions=(provisional,)
        )
        self.assertIs(
            construction.identity_resolutions[0].status,
            IdentityResolutionStatus.PROVISIONAL,
        )
        self.assertFalse(hasattr(construction, "assessment"))

    def test_relation_preserves_roles_order_and_n_arity(self):
        third = InterpretationReferent(ReferentKind.REALITY, "reality:campus")
        candidate = RelationCandidate(
            "candidate:relation",
            self.interpretation,
            "OFFERS_AT",
            (
                RelationCandidateParticipant("provider", self.university_ref),
                RelationCandidateParticipant("offering", self.scholarship_ref),
                RelationCandidateParticipant("site", third),
            ),
        )
        university_resolution = self._resolution(
            "resolution:university",
            self.university_ref,
            IdentityResolutionStatus.RESOLVED,
            self.reality_university,
        )
        scholarship_resolution = self._resolution(
            "resolution:scholarship",
            self.scholarship_ref,
            IdentityResolutionStatus.RESOLVED,
            self.reality_scholarship,
        )
        construction = build_proposition_construction(
            candidate,
            self.now,
            identity_resolutions=(university_resolution, scholarship_resolution),
        )
        participants = construction.proposition.target.participants
        self.assertEqual(
            [(p.role, p.reality_ref) for p in participants],
            [
                ("provider", "reality:university-x"),
                ("offering", "reality:scholarship-y"),
                ("site", "reality:campus"),
            ],
        )

    def test_relation_with_unresolved_participant_is_not_finalized(self):
        candidate = RelationCandidate(
            "candidate:relation:blocked",
            self.interpretation,
            "OFFERS",
            (
                RelationCandidateParticipant("provider", self.university_ref),
                RelationCandidateParticipant("offering", self.scholarship_ref),
            ),
        )
        resolved = self._resolution(
            "resolution:provider",
            self.university_ref,
            IdentityResolutionStatus.RESOLVED,
            self.reality_university,
        )
        unresolved = self._resolution(
            "resolution:offering",
            self.scholarship_ref,
            IdentityResolutionStatus.UNRESOLVED,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, self.now, identity_resolutions=(resolved, unresolved)
            )

    def test_condition_keeps_referents_in_construction_lineage(self):
        candidate = ConditionCandidate(
            "candidate:condition",
            self.interpretation,
            "provider is accredited",
            referents=(self.university_ref,),
        )
        resolution = self._resolution(
            "resolution:condition",
            self.university_ref,
            IdentityResolutionStatus.PROVISIONAL,
            self.reality_university,
        )
        construction = build_proposition_construction(
            candidate, self.now, identity_resolutions=(resolution,)
        )
        self.assertIs(construction.proposition.kind, PropositionKind.CONDITION_APPLIES)
        self.assertEqual(
            construction.identity_resolutions[0].resolution_ref,
            "resolution:condition",
        )

    def test_condition_unresolved_referent_is_not_erased(self):
        candidate = ConditionCandidate(
            "candidate:condition:unresolved",
            self.interpretation,
            "provider is accredited",
            referents=(self.university_ref,),
        )
        resolution = self._resolution(
            "resolution:condition:unresolved",
            self.university_ref,
            IdentityResolutionStatus.UNRESOLVED,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, self.now, identity_resolutions=(resolution,)
            )

    def test_candidate_and_proposition_fingerprints_are_distinct(self):
        candidate = PropertyCandidate(
            "candidate:fingerprints",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        construction = build_proposition_construction(candidate, self.now)
        self.assertNotEqual(candidate.fingerprint, construction.proposition.fingerprint)

    def test_support_trace_reconstructs_full_observation_lineage(self):
        candidate = PropertyCandidate(
            "candidate:support",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "fee",
            "50 USD",
        )
        construction = build_proposition_construction(candidate, self.now)
        support, trace = build_knowledge_support(
            construction,
            candidate,
            "support:1",
            SupportDisposition.SUPPORTS,
        )
        self.assertEqual(trace.statement.statement_ref, self.statement.statement_ref)
        self.assertEqual(trace.passage.passage_ref, "passage:one")
        self.assertEqual(trace.artifact.artifact_ref, "artifact:one")
        self.assertEqual(trace.observation.observation_ref, "observation:one")
        self.assertEqual(trace.source.source_ref, "source:a")
        self.assertIs(
            validate_knowledge_support_lineage(
                support, trace, construction, candidate
            ),
            support,
        )

    def test_multiple_supports_can_target_same_proposition(self):
        candidate = PropertyCandidate(
            "candidate:multi-support",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "fee",
            "50 USD",
        )
        construction = build_proposition_construction(candidate, self.now)
        support_a, _ = build_knowledge_support(
            construction, candidate, "support:a", SupportDisposition.SUPPORTS
        )
        support_b, _ = build_knowledge_support(
            construction, candidate, "support:b", SupportDisposition.QUALIFIES
        )
        self.assertEqual(
            support_a.proposition_fingerprint,
            support_b.proposition_fingerprint,
        )
        self.assertNotEqual(support_a.support_ref, support_b.support_ref)

    def test_same_source_multiple_observations_remain_distinct(self):
        statement_2 = self._statement(
            self.source,
            "two",
            "University X offers Scholarship Y. Application fee: 50 USD.",
        )
        self.assertEqual(
            self.statement.passage.artifact.observation.source.source_ref,
            statement_2.passage.artifact.observation.source.source_ref,
        )
        self.assertNotEqual(
            self.statement.passage.artifact.observation.observation_ref,
            statement_2.passage.artifact.observation.observation_ref,
        )
        self.assertNotEqual(self.statement.statement_ref, statement_2.statement_ref)

    def test_different_sources_remain_distinct(self):
        source_b = Source(
            "source:b",
            SourceKind.PUBLICATION,
            locator="https://example.invalid/b",
        )
        statement_b = self._statement(source_b, "b", "Application fee: 50 USD.")
        self.assertNotEqual(
            self.statement.passage.artifact.observation.source.source_ref,
            statement_b.passage.artifact.observation.source.source_ref,
        )

    def test_interpretation_mode_does_not_choose_support_disposition(self):
        candidate = PropertyCandidate(
            "candidate:disposition",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "fee",
            "50 USD",
        )
        construction = build_proposition_construction(candidate, self.now)
        support, _ = build_knowledge_support(
            construction,
            candidate,
            "support:qualifies",
            SupportDisposition.QUALIFIES,
        )
        self.assertIs(self.interpretation.mode, InterpretationMode.EXPLICIT)
        self.assertIs(support.disposition, SupportDisposition.QUALIFIES)

    def test_no_assessment_or_fact_is_created_automatically(self):
        candidate = PropertyCandidate(
            "candidate:no-assessment",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "fee",
            "50 USD",
        )
        construction = build_proposition_construction(candidate, self.now)
        support, trace = build_knowledge_support(
            construction,
            candidate,
            "support:no-assessment",
            SupportDisposition.SUPPORTS,
        )
        for value in (construction, support, trace):
            self.assertNotIsInstance(value, PropositionAssessment)
        self.assertFalse(hasattr(construction, "fact"))
        self.assertFalse(hasattr(support, "assessment"))

    def test_pipeline_times_do_not_become_world_validity(self):
        candidate = PropertyCandidate(
            "candidate:no-validity-inference",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "effective_date",
            "2027-01-01",
        )
        construction = build_proposition_construction(candidate, self.now)
        self.assertIsNone(construction.proposition.validity)

    def test_explicit_temporal_validity_is_preserved(self):
        candidate = PropertyCandidate(
            "candidate:validity",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        validity = TemporalValidity(valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc))
        construction = build_proposition_construction(
            candidate, self.now, validity=validity
        )
        self.assertEqual(construction.proposition.validity, validity)

    def test_constructed_at_must_be_timezone_aware(self):
        candidate = PropertyCandidate(
            "candidate:naive",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, datetime(2026, 10, 2, 12, 0, 0)
            )

    def test_private_scope_never_becomes_public(self):
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        source = Source("source:private", SourceKind.CONNECTED_FILE, scope=private)
        statement = self._statement(source, "private", "Private statement")
        interpretation = Interpretation(
            "interpretation:private",
            statement,
            self.now,
            InterpretationMode.EXPLICIT,
        )
        candidate = PropertyCandidate(
            "candidate:private",
            interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        construction = build_proposition_construction(candidate, self.now)
        self.assertIs(construction.scope.visibility, ScopeVisibility.PRIVATE)
        self.assertEqual(construction.scope.context_ref, "profile:42")
        support, trace = build_knowledge_support(
            construction,
            candidate,
            "support:private",
            SupportDisposition.SUPPORTS,
        )
        validate_knowledge_support_lineage(support, trace, construction, candidate)
        self.assertIs(trace.scope.visibility, ScopeVisibility.PRIVATE)

    def test_incompatible_non_public_resolution_scopes_do_not_merge(self):
        private_a = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:a")
        private_b = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:b")
        source = Source("source:scope", SourceKind.CONNECTED_FILE, scope=private_a)
        statement = self._statement(source, "scope", "University X")
        mention = Mention("mention:scope", statement, "University X", start=0, end=12)
        interpretation = Interpretation(
            "interpretation:scope",
            statement,
            self.now,
            InterpretationMode.EXPLICIT,
            mentions=(mention,),
        )
        referent = InterpretationReferent(ReferentKind.MENTION, mention.mention_ref)
        candidate = PropertyCandidate(
            "candidate:scope",
            interpretation,
            referent,
            "status",
            "open",
        )
        resolution = IdentityResolution(
            "resolution:scope",
            referent,
            private_b,
            self.now,
            IdentityResolutionStatus.RESOLVED,
            reality=Reality("reality:x"),
            basis=(
                IdentityResolutionBasis(
                    IdentityResolutionBasisKind.MENTION, mention.mention_ref
                ),
            ),
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_construction(
                candidate, self.now, identity_resolutions=(resolution,)
            )

    def test_public_support_metadata_rejects_secrets_at_gate(self):
        candidate = PropertyCandidate(
            "candidate:secret",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        construction = build_proposition_construction(candidate, self.now)
        support, trace = build_knowledge_support(
            construction,
            candidate,
            "support:secret",
            SupportDisposition.SUPPORTS,
            metadata={"api_key": "do-not-store"},
        )
        with self.assertRaises(KnowledgeGateError):
            validate_knowledge_support_lineage(
                support, trace, construction, candidate
            )

    def test_unknown_is_not_false_none_closed_or_not_applicable(self):
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.FALSE)
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.CLOSED)
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.NOT_APPLICABLE)
        self.assertIsNot(KnowledgeValue.UNKNOWN, None)

    def test_not_found_observation_does_not_create_negative_proposition(self):
        attempt = ObservationAttempt(
            "attempt:not-found",
            self.source,
            self.now,
            ObservationAttemptOutcome.NOT_FOUND,
        )
        with self.assertRaises(MayeleContractError):
            Observation("observation:not-found", attempt, self.now)

    def test_identity_resolution_basis_is_not_knowledge_support(self):
        basis = IdentityResolutionBasis(
            IdentityResolutionBasisKind.MENTION,
            self.university.mention_ref,
        )
        self.assertNotIsInstance(basis, KnowledgeSupport)

    def test_construction_is_not_proposition(self):
        candidate = PropertyCandidate(
            "candidate:not-proposition",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        construction = build_proposition_construction(candidate, self.now)
        self.assertIsInstance(construction, PropositionConstruction)
        self.assertNotIsInstance(construction, Proposition)

    def test_support_trace_is_typed_and_not_opaque(self):
        candidate = PropertyCandidate(
            "candidate:typed-trace",
            self.interpretation,
            InterpretationReferent(ReferentKind.REALITY, "reality:x"),
            "status",
            "open",
        )
        construction = build_proposition_construction(candidate, self.now)
        support, trace = build_knowledge_support(
            construction,
            candidate,
            "support:typed",
            SupportDisposition.SUPPORTS,
        )
        self.assertIsInstance(trace, KnowledgeSupportTrace)
        self.assertEqual(trace.support_ref, support.support_ref)
        self.assertEqual(trace.source.source_ref, "source:a")
