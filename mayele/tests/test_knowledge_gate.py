from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.knowledge import (
    KnowledgeSupport,
    KnowledgeValue,
    Property,
    Proposition,
    PropositionKind,
    Reality,
    SupportDisposition,
    TemporalValidity,
)
from mayele.knowledge.gate import KnowledgeCandidate, validate_candidate


class KnowledgeGateTests(TestCase):
    def setUp(self):
        self.proposition = Proposition(
            PropositionKind.REALITY_EXISTS,
            Reality("reality:visa"),
        )

    def test_valid_candidate_is_accepted(self):
        support = KnowledgeSupport(
            self.proposition.fingerprint,
            "observation:1",
            SupportDisposition.SUPPORTS,
        )
        accepted = validate_candidate(
            KnowledgeCandidate(
                proposition=self.proposition,
                supports=(support,),
                support_required=True,
            )
        )
        self.assertIs(accepted, self.proposition)

    def test_fingerprint_mismatch_is_rejected(self):
        with self.assertRaises(KnowledgeGateError):
            validate_candidate(
                KnowledgeCandidate(
                    proposition=self.proposition,
                    expected_fingerprint="0" * 64,
                )
            )

    def test_support_for_wrong_proposition_is_rejected(self):
        support = KnowledgeSupport(
            "f" * 64,
            "observation:1",
            SupportDisposition.SUPPORTS,
        )
        with self.assertRaises(KnowledgeGateError):
            validate_candidate(
                KnowledgeCandidate(self.proposition, supports=(support,))
            )

    def test_sensitive_metadata_is_rejected(self):
        support = KnowledgeSupport(
            self.proposition.fingerprint,
            "observation:1",
            SupportDisposition.SUPPORTS,
            metadata={"api_key": "should-never-cross-contract"},
        )
        with self.assertRaises(KnowledgeGateError):
            validate_candidate(
                KnowledgeCandidate(self.proposition, supports=(support,))
            )

    def test_authority_mutation_metadata_is_rejected(self):
        support = KnowledgeSupport(
            self.proposition.fingerprint,
            "observation:1",
            SupportDisposition.SUPPORTS,
            metadata={"grant_permission": True},
        )
        with self.assertRaises(KnowledgeGateError):
            validate_candidate(
                KnowledgeCandidate(self.proposition, supports=(support,))
            )

    def test_invalid_temporality_is_rejected_by_contract(self):
        now = datetime.now(timezone.utc)
        with self.assertRaises(MayeleContractError):
            TemporalValidity(
                valid_from=now,
                valid_until=now - timedelta(seconds=1),
            )

    def test_support_is_required_when_contract_demands_it(self):
        with self.assertRaises(KnowledgeGateError):
            validate_candidate(
                KnowledgeCandidate(
                    self.proposition,
                    support_required=True,
                )
            )

    def test_unknown_is_not_coerced_to_negative(self):
        proposition = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "visa_required", KnowledgeValue.UNKNOWN),
        )
        accepted = validate_candidate(KnowledgeCandidate(proposition))
        self.assertIs(accepted.target.value, KnowledgeValue.UNKNOWN)
        self.assertIsNot(accepted.target.value, False)
        self.assertIsNot(accepted.target.value, None)
