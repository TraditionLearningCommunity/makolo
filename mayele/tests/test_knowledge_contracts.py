from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.knowledge import (
    AssessmentStatus,
    Condition,
    KnowledgeSupport,
    KnowledgeValue,
    Property,
    Proposition,
    PropositionAssessment,
    PropositionKind,
    Reality,
    Relation,
    RelationParticipant,
    SupportDisposition,
)


class KnowledgeContractTests(TestCase):
    def test_reality_identity_is_independent_from_contextual_role(self):
        visa = Reality("reality:visa", "Visa")
        self.assertEqual(visa.reality_ref, "reality:visa")
        self.assertFalse(hasattr(visa, "requirement"))

    def test_same_visa_is_reusable_without_becoming_requirement(self):
        visa = Reality("reality:visa", "Visa")
        exists = Proposition(PropositionKind.REALITY_EXISTS, visa)
        condition = Condition("visa(reality:visa).valid == true")
        applies = Proposition(PropositionKind.CONDITION_APPLIES, condition)
        self.assertNotEqual(exists.fingerprint, applies.fingerprint)
        self.assertEqual(visa.reality_ref, "reality:visa")

    def test_proposition_is_immutable(self):
        proposition = Proposition(
            PropositionKind.REALITY_EXISTS, Reality("reality:x")
        )
        with self.assertRaises(FrozenInstanceError):
            proposition.kind = PropositionKind.PROPERTY_HOLDS

    def test_proposition_fingerprint_is_stable_and_source_independent(self):
        prop_a = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "deadline", "2027-01-15"),
        )
        prop_b = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "deadline", "2027-01-15"),
        )
        self.assertEqual(prop_a.fingerprint, prop_b.fingerprint)

    def test_multiple_supports_can_target_same_proposition(self):
        proposition = Proposition(
            PropositionKind.REALITY_EXISTS, Reality("reality:x")
        )
        supports = (
            KnowledgeSupport(
                proposition.fingerprint,
                "observation:1",
                SupportDisposition.SUPPORTS,
            ),
            KnowledgeSupport(
                proposition.fingerprint,
                "passage:2",
                SupportDisposition.QUALIFIES,
            ),
        )
        self.assertEqual(
            {support.proposition_fingerprint for support in supports},
            {proposition.fingerprint},
        )

    def test_contradictory_propositions_can_coexist(self):
        jan15 = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "deadline", "2027-01-15"),
        )
        jan20 = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "deadline", "2027-01-20"),
        )
        assessment = PropositionAssessment(
            jan15.fingerprint,
            AssessmentStatus.CONTRADICTORY,
            datetime.now(timezone.utc),
        )
        self.assertNotEqual(jan15.fingerprint, jan20.fingerprint)
        self.assertEqual(assessment.status, AssessmentStatus.CONTRADICTORY)

    def test_unknown_is_distinct_from_false_none_and_not_applicable(self):
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.FALSE)
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.NOT_APPLICABLE)
        self.assertIsNot(KnowledgeValue.UNKNOWN, KnowledgeValue.CLOSED)
        self.assertIsNot(KnowledgeValue.UNKNOWN, None)
        self.assertNotEqual(KnowledgeValue.UNKNOWN.value, False)

    def test_fact_is_not_a_primary_contract(self):
        import mayele.knowledge.contracts as contracts

        self.assertFalse(hasattr(contracts, "Fact"))
        self.assertFalse(hasattr(contracts, "FactRecord"))
        self.assertFalse(hasattr(contracts, "FactStore"))

    def test_relation_and_condition_are_not_true_by_construction(self):
        relation = Relation(
            "OFFERS",
            (
                RelationParticipant("provider", "reality:university"),
                RelationParticipant("offering", "reality:opportunity"),
            ),
        )
        condition = Condition("TOEFL.score >= 90")
        self.assertFalse(hasattr(relation, "is_true"))
        self.assertFalse(hasattr(condition, "is_true"))

    def test_relation_can_be_n_ary(self):
        relation = Relation(
            "ASSIGNS",
            (
                RelationParticipant("authority", "reality:a"),
                RelationParticipant("beneficiary", "reality:b"),
                RelationParticipant("resource", "reality:c"),
            ),
        )
        self.assertEqual(len(relation.participants), 3)

    def test_private_and_restricted_scope_are_preserved(self):
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        restricted = KnowledgeScope(
            ScopeVisibility.RESTRICTED, "research-context:7"
        )
        prop = Proposition(
            PropositionKind.REALITY_EXISTS,
            Reality("reality:x"),
            scope=private,
        )
        self.assertEqual(prop.scope.visibility, ScopeVisibility.PRIVATE)
        self.assertEqual(restricted.visibility, ScopeVisibility.RESTRICTED)
