import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.knowledge import (
    AssessmentStatus,
    KnowledgeSupport,
    KnowledgeSupportTrace,
    Property,
    Proposition,
    PropositionAssessment,
    PropositionAssessmentTrace,
    PropositionComparison,
    PropositionComparisonStatus,
    PropositionKind,
    SupportDisposition,
    TemporalValidity,
    build_proposition_assessment,
)
from mayele.knowledge.assessment_gate import (
    validate_assessment_history,
    validate_proposition_assessment,
)
from mayele.observation import (
    Observation,
    ObservationAttempt,
    ObservationAttemptOutcome,
    ObservedArtifact,
    ObservedStatement,
    Passage,
    Source,
    SourceKind,
)


class PropositionAssessmentTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        self.proposition = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:opportunity:x", "deadline", "2027-01-15"),
        )

    def _statement(self, ref="one", scope=None):
        scope = KnowledgeScope() if scope is None else scope
        source = Source(f"source:{ref}", SourceKind.WEB_PAGE, scope=scope)
        attempt = ObservationAttempt(
            f"attempt:{ref}", source, self.now, ObservationAttemptOutcome.SUCCESS
        )
        observation = Observation(f"observation:{ref}", attempt, self.now)
        artifact = ObservedArtifact(f"artifact:{ref}", observation, "text/plain")
        passage = Passage(f"passage:{ref}", artifact, "line=1")
        return ObservedStatement(
            f"statement:{ref}", passage, "Deadline is 15 January 2027."
        )

    def _support(self, ref="one", disposition=SupportDisposition.SUPPORTS, scope=None):
        support = KnowledgeSupport(
            self.proposition.fingerprint, f"support:{ref}", disposition
        )
        return support, KnowledgeSupportTrace(
            f"support:{ref}", self._statement(ref, scope)
        )

    def _build(self, status=AssessmentStatus.ESTABLISHED, ref="assessment:1", **kwargs):
        support, trace = self._support()
        kwargs.setdefault("supports", (support,))
        kwargs.setdefault("support_traces", (trace,))
        return build_proposition_assessment(
            self.proposition, status, self.now, assessment_ref=ref, **kwargs
        )

    def test_reuses_existing_contract_and_preserves_all_statuses(self):
        assessment, trace = self._build()
        self.assertIsInstance(assessment, PropositionAssessment)
        self.assertIsInstance(trace, PropositionAssessmentTrace)
        self.assertEqual(assessment.proposition_fingerprint, self.proposition.fingerprint)
        self.assertEqual(
            {item.value for item in AssessmentStatus},
            {"ESTABLISHED", "PARTIALLY_SUPPORTED", "CONTRADICTORY", "UNRESOLVED", "SUPERSEDED"},
        )
        self.assertFalse(hasattr(assessment, "fact"))

    def test_assessment_identity_time_rule_and_history_are_explicit(self):
        a1, t1 = self._build(ref="assessment:old")
        support, support_trace = self._support("later", SupportDisposition.CONTRADICTS)
        a2, t2 = build_proposition_assessment(
            self.proposition,
            AssessmentStatus.CONTRADICTORY,
            self.now + timedelta(hours=1),
            assessment_ref="assessment:new",
            supports=(support,),
            support_traces=(support_trace,),
            assessment_rule_ref="rule:explicit",
            assessment_rule_version="1",
            supersedes_assessment_ref=t1.assessment_ref,
        )
        history = validate_assessment_history((t1, t2))
        self.assertEqual((history[0].assessment, history[1].assessment), (a1, a2))
        self.assertIs(a1.status, AssessmentStatus.ESTABLISHED)
        with self.assertRaises(MayeleContractError):
            self._build(assessment_rule_version="2")
        with self.assertRaises(MayeleContractError):
            self._build(ref="assessment:self", supersedes_assessment_ref="assessment:self")
        with self.assertRaises(KnowledgeGateError):
            validate_assessment_history((t1, t1))

    def test_supports_are_exactly_the_ones_used_and_keep_my5_lineage(self):
        support, trace = self._support()
        assessment, assessment_trace = self._build()
        self.assertEqual(assessment_trace.support_refs, (support.support_ref,))
        self.assertEqual(trace.source.source_ref, "source:one")
        self.assertIs(
            validate_proposition_assessment(
                self.proposition,
                assessment,
                assessment_trace,
                supports=(support,),
                support_traces=(trace,),
            ),
            assessment,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.ESTABLISHED,
                self.now,
                assessment_ref="assessment:no-trace",
                supports=(support,),
            )
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.ESTABLISHED,
                self.now,
                assessment_ref="assessment:dup",
                supports=(support, support),
                support_traces=(trace,),
            )

    def test_status_is_never_derived_from_support_count_or_disposition(self):
        support, trace = self._support("contra", SupportDisposition.CONTRADICTS)
        unresolved, _ = build_proposition_assessment(
            self.proposition,
            AssessmentStatus.UNRESOLVED,
            self.now,
            assessment_ref="assessment:explicit-unresolved",
            supports=(support,),
            support_traces=(trace,),
        )
        self.assertIs(unresolved.status, AssessmentStatus.UNRESOLVED)
        partial, _ = self._build(AssessmentStatus.PARTIALLY_SUPPORTED)
        self.assertIs(partial.status, AssessmentStatus.PARTIALLY_SUPPORTED)
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.CONTRADICTORY,
                self.now,
                assessment_ref="assessment:no-basis",
            )

    def test_different_propositions_need_explicit_applicability_comparison(self):
        other = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:opportunity:x", "deadline", "2027-02-01"),
        )
        distinct = PropositionComparison(
            "comparison:distinct",
            self.proposition.fingerprint,
            other.fingerprint,
            PropositionComparisonStatus.DISTINCT_CONTEXT,
            self.now,
        )
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.CONTRADICTORY,
                self.now,
                assessment_ref="assessment:distinct",
                comparisons=(distinct,),
            )
        comparable = PropositionComparison(
            "comparison:comparable",
            self.proposition.fingerprint,
            other.fingerprint,
            PropositionComparisonStatus.COMPARABLE,
            self.now,
        )
        assessment, trace = build_proposition_assessment(
            self.proposition,
            AssessmentStatus.CONTRADICTORY,
            self.now,
            assessment_ref="assessment:comparable",
            comparisons=(comparable,),
        )
        self.assertIs(assessment.status, AssessmentStatus.CONTRADICTORY)
        self.assertEqual(trace.comparison_refs, ("comparison:comparable",))

    def test_superseded_is_historical_not_false_and_requires_successor(self):
        successor = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:opportunity:x", "deadline", "2027-02-01"),
        )
        assessment, trace = build_proposition_assessment(
            self.proposition,
            AssessmentStatus.SUPERSEDED,
            self.now,
            assessment_ref="assessment:superseded",
            successor_proposition_fingerprint=successor.fingerprint,
        )
        self.assertIs(assessment.status, AssessmentStatus.SUPERSEDED)
        self.assertNotEqual(assessment.status.value, "FALSE")
        self.assertEqual(trace.successor_proposition_fingerprint, successor.fingerprint)
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.SUPERSEDED,
                self.now,
                assessment_ref="assessment:no-successor",
            )

    def test_scope_never_widens_and_incompatible_private_contexts_do_not_merge(self):
        private_a = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:a")
        private_b = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:b")
        proposition = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:private", "status", "active"),
            scope=private_a,
        )
        support = KnowledgeSupport(
            proposition.fingerprint, "support:private", SupportDisposition.SUPPORTS
        )
        trace_a = KnowledgeSupportTrace("support:private", self._statement("a", private_a))
        _, assessment_trace = build_proposition_assessment(
            proposition,
            AssessmentStatus.ESTABLISHED,
            self.now,
            assessment_ref="assessment:private",
            supports=(support,),
            support_traces=(trace_a,),
        )
        self.assertEqual(assessment_trace.scope, private_a)
        trace_b = KnowledgeSupportTrace("support:private", self._statement("b", private_b))
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                proposition,
                AssessmentStatus.ESTABLISHED,
                self.now,
                assessment_ref="assessment:incompatible",
                supports=(support,),
                support_traces=(trace_b,),
            )

    def test_sensitive_public_metadata_and_authority_mutation_are_rejected(self):
        support, support_trace = self._support()
        for metadata in ({"api_key": "no"}, {"grant_permission": True}):
            assessment, trace = build_proposition_assessment(
                self.proposition,
                AssessmentStatus.ESTABLISHED,
                self.now,
                assessment_ref=f"assessment:{next(iter(metadata))}",
                supports=(support,),
                support_traces=(support_trace,),
                metadata=metadata,
            )
            with self.assertRaises(KnowledgeGateError):
                validate_proposition_assessment(
                    self.proposition,
                    assessment,
                    trace,
                    supports=(support,),
                    support_traces=(support_trace,),
                )

    def test_assessed_at_is_not_world_validity(self):
        validity = TemporalValidity(valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc))
        proposition = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property("reality:x", "status", "open"),
            validity=validity,
        )
        support = KnowledgeSupport(
            proposition.fingerprint, "support:validity", SupportDisposition.SUPPORTS
        )
        trace = KnowledgeSupportTrace("support:validity", self._statement("validity"))
        build_proposition_assessment(
            proposition,
            AssessmentStatus.ESTABLISHED,
            self.now,
            assessment_ref="assessment:validity",
            supports=(support,),
            support_traces=(trace,),
        )
        self.assertEqual(proposition.validity, validity)
        with self.assertRaises(MayeleContractError):
            build_proposition_assessment(
                self.proposition,
                AssessmentStatus.UNRESOLVED,
                datetime(2026, 10, 2, 10, 0),
                assessment_ref="assessment:naive",
            )

    def test_imports_stay_framework_and_legacy_free(self):
        root = Path(__file__).resolve().parents[2]
        code = (
            "import sys; import mayele.knowledge; "
            "forbidden=('django','prospector','observer','interpreter','resolver','web_research','orchestration','projector'); "
            "assert not any(n==p or n.startswith(p+'.') for p in forbidden for n in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=root, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
