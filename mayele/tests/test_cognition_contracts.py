from datetime import datetime, timezone
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.cognition import (
    CognitionCandidate,
    ConditionCandidate,
    Interpretation,
    InterpretationMode,
    InterpretationReferent,
    InterpretationTransformation,
    PropertyCandidate,
    RealityCandidate,
    ReferentKind,
    RelationCandidate,
    RelationCandidateParticipant,
    validate_candidate,
)
from mayele.knowledge import (
    Condition,
    KnowledgeSupport,
    KnowledgeValue,
    Property,
    Proposition,
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


class CognitionContractTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        source = Source("source:admissions", SourceKind.WEB_PAGE)
        attempt = ObservationAttempt(
            "attempt:1",
            source,
            self.now,
            ObservationAttemptOutcome.SUCCESS,
        )
        observation = Observation("observation:1", attempt, self.now)
        artifact = ObservedArtifact("artifact:1", observation, "text/plain")
        passage = Passage("passage:1", artifact, "line=1")
        self.statement = ObservedStatement(
            "statement:1",
            passage,
            "University X offers Program Y. Applications close on 31 January 2027.",
        )
        university_start = self.statement.text.index("University X")
        program_start = self.statement.text.index("Program Y")
        self.university = Mention(
            "mention:university",
            self.statement,
            "University X",
            start=university_start,
            end=university_start + len("University X"),
        )
        self.program = Mention(
            "mention:program",
            self.statement,
            "Program Y",
            start=program_start,
            end=program_start + len("Program Y"),
        )
        self.interpretation = Interpretation(
            "interpretation:1",
            self.statement,
            self.now,
            InterpretationMode.NORMALIZED,
            mentions=(self.university, self.program),
            method_ref="rule:admissions-vocabulary",
            method_version="1",
        )
        self.university_ref = InterpretationReferent(
            ReferentKind.MENTION, self.university.mention_ref
        )
        self.program_ref = InterpretationReferent(
            ReferentKind.MENTION, self.program.mention_ref
        )

    def test_observed_statement_is_not_interpretation_or_candidate(self):
        self.assertNotIsInstance(self.statement, Interpretation)
        candidate = RealityCandidate(
            "candidate:university",
            self.interpretation,
            source_referent=self.university_ref,
        )
        self.assertNotIsInstance(self.statement, RealityCandidate)
        self.assertNotEqual(type(self.statement), type(candidate))

    def test_mention_does_not_automatically_become_reality_candidate(self):
        self.assertNotIsInstance(self.university, RealityCandidate)
        self.assertFalse(hasattr(self.university, "candidate_ref"))

    def test_reality_candidate_is_distinct_from_reality(self):
        candidate = RealityCandidate(
            "candidate:university",
            self.interpretation,
            source_referent=self.university_ref,
            label="University X",
        )
        self.assertNotIsInstance(candidate, Reality)
        self.assertFalse(hasattr(candidate, "reality_ref"))

    def test_property_candidate_accepts_unresolved_subject(self):
        candidate = PropertyCandidate(
            "candidate:deadline",
            self.interpretation,
            self.program_ref,
            "application_deadline",
            "2027-01-31",
        )
        self.assertEqual(candidate.subject.kind, ReferentKind.MENTION)
        self.assertFalse(hasattr(candidate, "reality_ref"))
        self.assertNotIsInstance(candidate, Property)

    def test_relation_candidate_supports_unresolved_n_ary_participants(self):
        third = InterpretationReferent(
            ReferentKind.REALITY_CANDIDATE, "candidate:catalogue"
        )
        candidate = RelationCandidate(
            "candidate:relation",
            self.interpretation,
            "OFFERS",
            (
                RelationCandidateParticipant("provider", self.university_ref),
                RelationCandidateParticipant("offering", self.program_ref),
                RelationCandidateParticipant("catalogue", third),
            ),
        )
        self.assertEqual(len(candidate.participants), 3)
        self.assertEqual(candidate.participants[0].role, "provider")
        self.assertNotIsInstance(candidate, Relation)

    def test_condition_candidate_is_distinct_from_established_condition(self):
        candidate = ConditionCandidate(
            "candidate:condition",
            self.interpretation,
            "age >= 18",
            referents=(self.program_ref,),
        )
        self.assertNotIsInstance(candidate, Condition)

    def test_interpretation_preserves_statement_and_mentions_lineage(self):
        self.assertIs(self.interpretation.statement, self.statement)
        self.assertEqual(
            tuple(item.mention_ref for item in self.interpretation.mentions),
            ("mention:university", "mention:program"),
        )

    def test_interpreted_at_must_be_timezone_aware(self):
        with self.assertRaises(MayeleContractError):
            Interpretation(
                "interpretation:naive",
                self.statement,
                datetime(2026, 10, 1, 10, 0, 0),
                InterpretationMode.EXPLICIT,
            )

    def test_interpretation_modes_are_explicit(self):
        modes = {
            InterpretationMode.EXPLICIT,
            InterpretationMode.NORMALIZED,
            InterpretationMode.INFERRED,
        }
        self.assertEqual(len(modes), 3)

    def test_translation_is_explicitly_signalled_as_transformation(self):
        translated = Interpretation(
            "interpretation:translated",
            self.statement,
            self.now,
            InterpretationMode.NORMALIZED,
            transformation=InterpretationTransformation.TRANSLATION,
        )
        self.assertEqual(
            translated.transformation, InterpretationTransformation.TRANSLATION
        )

    def test_private_scope_propagates_and_cannot_widen(self):
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        source = Source(
            "source:private",
            SourceKind.CONNECTED_FILE,
            scope=private,
        )
        attempt = ObservationAttempt(
            "attempt:private",
            source,
            self.now,
            ObservationAttemptOutcome.SUCCESS,
        )
        observation = Observation("observation:private", attempt, self.now)
        artifact = ObservedArtifact("artifact:private", observation, "text/plain")
        passage = Passage("passage:private", artifact, "line=1")
        statement = ObservedStatement("statement:private", passage, "Private statement")
        interpretation = Interpretation(
            "interpretation:private",
            statement,
            self.now,
            InterpretationMode.EXPLICIT,
        )
        self.assertEqual(interpretation.scope, private)

        with self.assertRaises(MayeleContractError):
            RealityCandidate(
                "candidate:public",
                interpretation,
                scope=KnowledgeScope(ScopeVisibility.PUBLIC),
            )

    def test_candidate_does_not_create_proposition_or_knowledge_support(self):
        candidate = RelationCandidate(
            "candidate:relation",
            self.interpretation,
            "OFFERS",
            (
                RelationCandidateParticipant("provider", self.university_ref),
                RelationCandidateParticipant("offering", self.program_ref),
            ),
        )
        self.assertNotIsInstance(candidate, Proposition)
        self.assertNotIsInstance(candidate, KnowledgeSupport)
        self.assertFalse(hasattr(candidate, "proposition"))

    def test_absence_is_not_silently_encoded_as_none(self):
        with self.assertRaises(MayeleContractError):
            PropertyCandidate(
                "candidate:fee",
                self.interpretation,
                self.program_ref,
                "application_fee",
                None,
            )

    def test_unknown_remains_distinct_from_negative_values(self):
        candidate = PropertyCandidate(
            "candidate:unknown",
            self.interpretation,
            self.program_ref,
            "application_fee",
            KnowledgeValue.UNKNOWN,
        )
        self.assertIs(candidate.value, KnowledgeValue.UNKNOWN)
        self.assertIsNot(candidate.value, KnowledgeValue.FALSE)
        self.assertIsNot(candidate.value, KnowledgeValue.NOT_APPLICABLE)
        self.assertIsNot(candidate.value, None)

    def test_normalized_interpretation_does_not_modify_verbatim_statement(self):
        original = self.statement.text
        PropertyCandidate(
            "candidate:deadline",
            self.interpretation,
            self.program_ref,
            "application_deadline",
            "2027-01-31",
        )
        self.assertEqual(self.statement.text, original)

    def test_candidate_fingerprint_is_deterministic_and_method_independent(self):
        second_interpretation = Interpretation(
            "interpretation:2",
            self.statement,
            self.now,
            InterpretationMode.NORMALIZED,
            mentions=(self.university, self.program),
            method_ref="manual-review",
            method_version="7",
        )
        left = PropertyCandidate(
            "candidate:left",
            self.interpretation,
            self.program_ref,
            "application_deadline",
            "2027-01-31",
        )
        right = PropertyCandidate(
            "candidate:right",
            second_interpretation,
            self.program_ref,
            "application_deadline",
            "2027-01-31",
        )
        self.assertEqual(left.fingerprint, right.fingerprint)
        self.assertNotEqual(
            self.interpretation.execution_fingerprint,
            second_interpretation.execution_fingerprint,
        )

    def test_relation_candidate_rejects_invalid_participants(self):
        with self.assertRaises(MayeleContractError):
            RelationCandidate(
                "candidate:invalid",
                self.interpretation,
                "OFFERS",
                (RelationCandidateParticipant("provider", self.university_ref),),
            )

    def test_gate_rejects_mention_outside_interpretation_lineage(self):
        external = InterpretationReferent(ReferentKind.MENTION, "mention:external")
        candidate = PropertyCandidate(
            "candidate:deadline",
            self.interpretation,
            external,
            "application_deadline",
            "2027-01-31",
        )
        with self.assertRaises(MayeleContractError):
            validate_candidate(CognitionCandidate(candidate))

    def test_gate_accepts_structurally_valid_candidate_only(self):
        candidate = RelationCandidate(
            "candidate:relation",
            self.interpretation,
            "OFFERS",
            (
                RelationCandidateParticipant("provider", self.university_ref),
                RelationCandidateParticipant("offering", self.program_ref),
            ),
        )
        accepted = validate_candidate(
            CognitionCandidate(
                candidate,
                expected_fingerprint=candidate.fingerprint,
            )
        )
        self.assertIs(accepted, candidate)
        self.assertFalse(hasattr(accepted, "is_true"))
