from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.cognition import InterpretationReferent, ReferentKind
from mayele.identity import (
    IdentityResolution,
    IdentityResolutionBasis,
    IdentityResolutionBasisKind,
    IdentityResolutionStatus,
)
from mayele.knowledge import (
    AssessmentStatus,
    KnowledgeFacetState,
    KnowledgeFacetStatus,
    Property,
    Proposition,
    PropositionAssessment,
    PropositionAssessmentTrace,
    PropositionKind,
    Reality,
    ResearchGapReason,
    ResearchGapResolutionKind,
    ResearchGapTarget,
    ResearchGapTargetKind,
    RevalidationReason,
    build_knowledge_completeness,
    build_knowledge_state,
    build_research_gap,
    build_revalidation_need,
    resolve_research_gap,
    validate_knowledge_completeness,
    validate_knowledge_state,
    validate_research_gap,
    validate_revalidation_need,
)


class MY7KnowledgeStateGapTests(TestCase):
    def setUp(self):
        self.t1 = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        self.t2 = self.t1 + timedelta(hours=1)
        self.t3 = self.t2 + timedelta(hours=1)
        self.reality = Reality("reality:opportunity:x")

    def proposition(self, attribute, value, scope=None):
        return Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property(self.reality.reality_ref, attribute, value),
            scope=scope or KnowledgeScope(),
        )

    def assessment(self, ref, proposition, status, at, supersedes=None, scope=None):
        support_refs = ()
        comparison_refs = ()
        if status in (
            AssessmentStatus.ESTABLISHED,
            AssessmentStatus.PARTIALLY_SUPPORTED,
        ):
            support_refs = (f"support:{ref}",)
        elif status is AssessmentStatus.CONTRADICTORY:
            comparison_refs = (f"comparison:{ref}",)
        return PropositionAssessmentTrace(
            ref,
            PropositionAssessment(proposition.fingerprint, status, at),
            support_refs=support_refs,
            comparison_refs=comparison_refs,
            supersedes_assessment_ref=supersedes,
            scope=scope or proposition.scope,
        )

    def resolution(self, ref, status, at, supersedes=None, scope=None):
        scope = scope or KnowledgeScope()
        referent = InterpretationReferent(ReferentKind.MENTION, "mention:x")
        return IdentityResolution(
            ref,
            referent,
            scope,
            at,
            status,
            reality=None if status is IdentityResolutionStatus.UNRESOLVED else self.reality,
            basis=(
                IdentityResolutionBasis(
                    IdentityResolutionBasisKind.MENTION, referent.ref
                ),
            ),
            supersedes_resolution_ref=supersedes,
            scope=scope,
        )

    def unknown_completeness(self, facet="deadline", at=None, scope=None):
        at = at or self.t1
        scope = scope or KnowledgeScope()
        return build_knowledge_completeness(
            self.reality,
            at,
            facets=(
                KnowledgeFacetState(
                    facet, KnowledgeFacetStatus.UNKNOWN, at, scope=scope
                ),
            ),
            scope=scope,
        )

    def test_completeness_exact_statuses_and_no_global_score(self):
        self.assertEqual(
            set(KnowledgeFacetStatus),
            {
                KnowledgeFacetStatus.KNOWN,
                KnowledgeFacetStatus.PARTIALLY_KNOWN,
                KnowledgeFacetStatus.UNKNOWN,
                KnowledgeFacetStatus.CONTRADICTORY,
                KnowledgeFacetStatus.NOT_APPLICABLE,
            },
        )
        self.assertNotIn(
            KnowledgeFacetStatus.UNKNOWN.value,
            (False, None, "CLOSED", KnowledgeFacetStatus.NOT_APPLICABLE.value),
        )
        completeness = self.unknown_completeness()
        for name in ("score", "percentage", "knowledge_score", "completeness_score"):
            self.assertFalse(hasattr(completeness, name))

    def test_mixed_completeness_is_facet_wise_and_traceable(self):
        deadline = self.proposition("deadline", "2027-01-15")
        eligibility = self.proposition("eligibility", "age>=18")
        capacity = self.proposition("capacity", "conflict")
        a_deadline = self.assessment(
            "assessment:deadline", deadline, AssessmentStatus.ESTABLISHED, self.t1
        )
        a_eligibility = self.assessment(
            "assessment:eligibility",
            eligibility,
            AssessmentStatus.PARTIALLY_SUPPORTED,
            self.t1,
        )
        a_capacity = self.assessment(
            "assessment:capacity",
            capacity,
            AssessmentStatus.CONTRADICTORY,
            self.t1,
        )
        completeness = build_knowledge_completeness(
            self.reality,
            self.t1,
            facets=(
                KnowledgeFacetState(
                    "deadline",
                    KnowledgeFacetStatus.KNOWN,
                    self.t1,
                    (deadline.fingerprint,),
                    (a_deadline.assessment_ref,),
                ),
                KnowledgeFacetState("fee", KnowledgeFacetStatus.UNKNOWN, self.t1),
                KnowledgeFacetState(
                    "eligibility",
                    KnowledgeFacetStatus.PARTIALLY_KNOWN,
                    self.t1,
                    (eligibility.fingerprint,),
                    (a_eligibility.assessment_ref,),
                ),
                KnowledgeFacetState(
                    "capacity",
                    KnowledgeFacetStatus.CONTRADICTORY,
                    self.t1,
                    (capacity.fingerprint,),
                    (a_capacity.assessment_ref,),
                ),
                KnowledgeFacetState(
                    "access",
                    KnowledgeFacetStatus.NOT_APPLICABLE,
                    self.t1,
                    applicability_basis_refs=("applicability:free-event",),
                ),
            ),
        )
        validate_knowledge_completeness(
            self.reality,
            completeness,
            propositions=(deadline, eligibility, capacity),
            assessment_traces=(a_deadline, a_eligibility, a_capacity),
        )
        self.assertEqual(
            [f.status for f in completeness.facets],
            [
                KnowledgeFacetStatus.KNOWN,
                KnowledgeFacetStatus.UNKNOWN,
                KnowledgeFacetStatus.PARTIALLY_KNOWN,
                KnowledgeFacetStatus.CONTRADICTORY,
                KnowledgeFacetStatus.NOT_APPLICABLE,
            ],
        )

    def test_known_rejects_unresolved_assessment_lineage(self):
        proposition = self.proposition("deadline", "unknown")
        unresolved = self.assessment(
            "assessment:unresolved-known",
            proposition,
            AssessmentStatus.UNRESOLVED,
            self.t1,
        )
        completeness = build_knowledge_completeness(
            self.reality,
            self.t1,
            facets=(
                KnowledgeFacetState(
                    "deadline",
                    KnowledgeFacetStatus.KNOWN,
                    self.t1,
                    (proposition.fingerprint,),
                    (unresolved.assessment_ref,),
                ),
            ),
        )
        with self.assertRaises(KnowledgeGateError):
            validate_knowledge_completeness(
                self.reality,
                completeness,
                propositions=(proposition,),
                assessment_traces=(unresolved,),
            )

    def test_state_requires_explicit_lineage_selection(self):
        proposition = self.proposition("deadline", "2027-01-15")
        trace = self.assessment(
            "assessment:explicit-lineage",
            proposition,
            AssessmentStatus.ESTABLISHED,
            self.t1,
        )
        with self.assertRaises(MayeleContractError):
            build_knowledge_state(
                self.reality,
                self.t1,
                state_ref="state:implicit-lineage",
                completeness=self.unknown_completeness(),
                assessment_traces=(trace,),
            )

    def test_state_does_not_absorb_unselected_foreign_lineage(self):
        relevant = self.assessment(
            "assessment:relevant",
            self.proposition("deadline", "2027-01-15"),
            AssessmentStatus.UNRESOLVED,
            self.t1,
        )
        other_reality = Reality("reality:other")
        foreign_proposition = Proposition(
            PropositionKind.PROPERTY_HOLDS,
            Property(other_reality.reality_ref, "deadline", "2027-02-01"),
        )
        foreign = self.assessment(
            "assessment:foreign",
            foreign_proposition,
            AssessmentStatus.UNRESOLVED,
            self.t1,
        )
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:explicit-lineage",
            completeness=self.unknown_completeness(),
            assessment_traces=(relevant, foreign),
            lineage_assessment_refs=(relevant.assessment_ref,),
        )
        self.assertEqual(
            state.effective_assessment_refs, (relevant.assessment_ref,)
        )

    def test_not_applicable_requires_basis_and_unknown_does_not(self):
        with self.assertRaises(MayeleContractError):
            KnowledgeFacetState(
                "economic", KnowledgeFacetStatus.NOT_APPLICABLE, self.t1
            )
        state = KnowledgeFacetState(
            "economic", KnowledgeFacetStatus.UNKNOWN, self.t1
        )
        self.assertIs(state.status, KnowledgeFacetStatus.UNKNOWN)

    def test_known_partial_contradictory_require_assessment_lineage(self):
        for status in (
            KnowledgeFacetStatus.KNOWN,
            KnowledgeFacetStatus.PARTIALLY_KNOWN,
            KnowledgeFacetStatus.CONTRADICTORY,
        ):
            with self.subTest(status=status), self.assertRaises(MayeleContractError):
                KnowledgeFacetState("facet", status, self.t1)

    def test_completeness_gate_checks_assessment_refs_time_and_scope(self):
        proposition = self.proposition("deadline", "2027-01-15")
        facet = KnowledgeFacetState(
            "deadline",
            KnowledgeFacetStatus.KNOWN,
            self.t1,
            (proposition.fingerprint,),
            ("assessment:x",),
        )
        completeness = build_knowledge_completeness(
            self.reality, self.t1, facets=(facet,)
        )
        with self.assertRaises(KnowledgeGateError):
            validate_knowledge_completeness(
                self.reality, completeness, propositions=(proposition,)
            )
        future = self.assessment(
            "assessment:x", proposition, AssessmentStatus.ESTABLISHED, self.t2
        )
        with self.assertRaises(KnowledgeGateError):
            validate_knowledge_completeness(
                self.reality,
                completeness,
                propositions=(proposition,),
                assessment_traces=(future,),
            )
        private_a = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:a")
        private_b = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:b")
        with self.assertRaises(MayeleContractError):
            build_knowledge_completeness(
                self.reality,
                self.t1,
                facets=(
                    KnowledgeFacetState(
                        "a", KnowledgeFacetStatus.UNKNOWN, self.t1, scope=private_a
                    ),
                    KnowledgeFacetState(
                        "b", KnowledgeFacetStatus.UNKNOWN, self.t1, scope=private_b
                    ),
                ),
            )

    def test_state_as_of_uses_explicit_assessment_supersession(self):
        proposition = self.proposition("deadline", "2027-01-15")
        a1 = self.assessment(
            "assessment:t1",
            proposition,
            AssessmentStatus.PARTIALLY_SUPPORTED,
            self.t1,
        )
        a2 = self.assessment(
            "assessment:t2",
            proposition,
            AssessmentStatus.ESTABLISHED,
            self.t2,
            supersedes=a1.assessment_ref,
        )
        s1 = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:t1",
            completeness=self.unknown_completeness(),
            assessment_traces=(a1, a2),
            lineage_assessment_refs=(a1.assessment_ref, a2.assessment_ref),
        )
        self.assertEqual(s1.effective_assessment_refs, (a1.assessment_ref,))
        s2 = build_knowledge_state(
            self.reality,
            self.t2,
            state_ref="state:t2",
            completeness=self.unknown_completeness(at=self.t2),
            assessment_traces=(a1, a2),
            lineage_assessment_refs=(a1.assessment_ref, a2.assessment_ref),
        )
        self.assertEqual(s2.effective_assessment_refs, (a2.assessment_ref,))
        self.assertIs(a1.assessment.status, AssessmentStatus.PARTIALLY_SUPPORTED)
        self.assertIs(
            validate_knowledge_state(
                self.reality,
                s2,
                assessment_traces=(a1, a2),
                lineage_assessment_refs=(a1.assessment_ref, a2.assessment_ref),
            ),
            s2,
        )

    def test_state_keeps_multiple_terminal_assessments(self):
        p1 = self.proposition("fee", "50")
        p2 = self.proposition("fee", "60")
        a1 = self.assessment(
            "assessment:a", p1, AssessmentStatus.ESTABLISHED, self.t1
        )
        a2 = self.assessment(
            "assessment:b", p2, AssessmentStatus.ESTABLISHED, self.t2
        )
        state = build_knowledge_state(
            self.reality,
            self.t2,
            state_ref="state:terminals",
            completeness=self.unknown_completeness("fee", at=self.t2),
            assessment_traces=(a2, a1),
            lineage_assessment_refs=(a2.assessment_ref, a1.assessment_ref),
        )
        self.assertEqual(
            state.effective_assessment_refs, ("assessment:a", "assessment:b")
        )

    def test_state_identity_supersession_future_exclusion_and_provisional(self):
        r1 = self.resolution(
            "resolution:t1", IdentityResolutionStatus.PROVISIONAL, self.t1
        )
        r2 = self.resolution(
            "resolution:t2",
            IdentityResolutionStatus.RESOLVED,
            self.t2,
            supersedes=r1.resolution_ref,
        )
        r3 = self.resolution(
            "resolution:t3",
            IdentityResolutionStatus.RESOLVED,
            self.t3,
            supersedes=r2.resolution_ref,
        )
        s1 = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:r1",
            completeness=self.unknown_completeness(),
            identity_resolutions=(r1, r2, r3),
            lineage_identity_resolution_refs=(
                r1.resolution_ref,
                r2.resolution_ref,
                r3.resolution_ref,
            ),
        )
        self.assertEqual(
            s1.effective_identity_resolution_refs, (r1.resolution_ref,)
        )
        self.assertIs(r1.status, IdentityResolutionStatus.PROVISIONAL)

    def test_state_is_reproducible_timezone_aware_and_not_fact(self):
        with self.assertRaises(MayeleContractError):
            build_knowledge_state(
                self.reality,
                datetime(2026, 10, 2, 12, 0),
                state_ref="state:naive",
                completeness=self.unknown_completeness(),
            )
        first = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:stable",
            completeness=self.unknown_completeness(),
        )
        second = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:stable",
            completeness=self.unknown_completeness(),
        )
        self.assertEqual(first, second)
        self.assertFalse(hasattr(first, "fact"))

    def test_unknown_requires_explicit_need_and_not_applicable_never_becomes_gap(self):
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:unknown",
            completeness=self.unknown_completeness(),
        )
        with self.assertRaises(MayeleContractError):
            build_research_gap(
                state,
                ResearchGapTarget(ResearchGapTargetKind.FACET, "deadline"),
                ResearchGapReason.UNKNOWN,
                self.t1,
                gap_ref="gap:no-trigger",
                basis_refs=("deadline",),
            )
        gap = build_research_gap(
            state,
            ResearchGapTarget(ResearchGapTargetKind.FACET, "deadline"),
            ResearchGapReason.UNKNOWN,
            self.t1,
            gap_ref="gap:deadline",
            basis_refs=("deadline",),
            trigger_ref="need:accessibility-decision",
        )
        self.assertEqual(gap.reason, ResearchGapReason.UNKNOWN)
        na = build_knowledge_completeness(
            self.reality,
            self.t1,
            facets=(
                KnowledgeFacetState(
                    "access",
                    KnowledgeFacetStatus.NOT_APPLICABLE,
                    self.t1,
                    applicability_basis_refs=("applicability:free-event",),
                ),
            ),
        )
        state_na = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:na",
            completeness=na,
        )
        with self.assertRaises(MayeleContractError):
            build_research_gap(
                state_na,
                ResearchGapTarget(ResearchGapTargetKind.FACET, "access"),
                ResearchGapReason.UNKNOWN,
                self.t1,
                gap_ref="gap:bad",
                basis_refs=("access",),
                trigger_ref="need:bad",
            )

    def test_contradictory_and_partial_gaps_are_explicit(self):
        proposition = self.proposition("capacity", "conflict")
        trace = self.assessment(
            "assessment:capacity",
            proposition,
            AssessmentStatus.CONTRADICTORY,
            self.t1,
        )
        for status, reason in (
            (
                KnowledgeFacetStatus.PARTIALLY_KNOWN,
                ResearchGapReason.PARTIALLY_KNOWN,
            ),
            (
                KnowledgeFacetStatus.CONTRADICTORY,
                ResearchGapReason.CONTRADICTORY,
            ),
        ):
            completeness = build_knowledge_completeness(
                self.reality,
                self.t1,
                facets=(
                    KnowledgeFacetState(
                        "capacity",
                        status,
                        self.t1,
                        (proposition.fingerprint,),
                        (trace.assessment_ref,),
                    ),
                ),
            )
            state = build_knowledge_state(
                self.reality,
                self.t1,
                state_ref=f"state:{status.value}",
                completeness=completeness,
                assessment_traces=(trace,),
                lineage_assessment_refs=(trace.assessment_ref,),
            )
            gap = build_research_gap(
                state,
                ResearchGapTarget(ResearchGapTargetKind.FACET, "capacity"),
                reason,
                self.t1,
                gap_ref=f"gap:{status.value}",
                basis_refs=("capacity",),
                trigger_ref="need:capacity" if reason is ResearchGapReason.PARTIALLY_KNOWN else None,
            )
            self.assertIs(gap.reason, reason)

    def test_unresolved_assessment_and_identity_can_be_gap_bases(self):
        proposition = self.proposition("deadline", "unknown")
        assessment = self.assessment(
            "assessment:unresolved",
            proposition,
            AssessmentStatus.UNRESOLVED,
            self.t1,
        )
        identity = self.resolution(
            "resolution:unresolved",
            IdentityResolutionStatus.UNRESOLVED,
            self.t1,
        )
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:unresolved",
            completeness=self.unknown_completeness(),
            assessment_traces=(assessment,),
            identity_resolutions=(identity,),
            lineage_assessment_refs=(assessment.assessment_ref,),
            lineage_identity_resolution_refs=(identity.resolution_ref,),
        )
        gap_a = build_research_gap(
            state,
            ResearchGapTarget(
                ResearchGapTargetKind.PROPOSITION, proposition.fingerprint
            ),
            ResearchGapReason.UNRESOLVED_ASSESSMENT,
            self.t1,
            gap_ref="gap:assessment",
            basis_refs=(assessment.assessment_ref,),
            assessment_traces=(assessment,),
        )
        gap_i = build_research_gap(
            state,
            ResearchGapTarget(
                ResearchGapTargetKind.IDENTITY, identity.resolution_ref
            ),
            ResearchGapReason.UNRESOLVED_IDENTITY,
            self.t1,
            gap_ref="gap:identity",
            basis_refs=(identity.resolution_ref,),
            identity_resolutions=(identity,),
        )
        validate_research_gap(
            state, gap_a, assessment_traces=(assessment,)
        )
        self.assertIs(gap_i.reason, ResearchGapReason.UNRESOLVED_IDENTITY)

    def test_provisional_identity_does_not_force_gap(self):
        identity = self.resolution(
            "resolution:provisional",
            IdentityResolutionStatus.PROVISIONAL,
            self.t1,
        )
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:provisional",
            completeness=self.unknown_completeness(),
            identity_resolutions=(identity,),
            lineage_identity_resolution_refs=(identity.resolution_ref,),
        )
        self.assertFalse(hasattr(state, "research_gaps"))
        with self.assertRaises(MayeleContractError):
            build_research_gap(
                state,
                ResearchGapTarget(
                    ResearchGapTargetKind.IDENTITY, identity.resolution_ref
                ),
                ResearchGapReason.PROVISIONAL_IDENTITY,
                self.t1,
                gap_ref="gap:implicit",
                basis_refs=(identity.resolution_ref,),
                identity_resolutions=(identity,),
            )
        gap = build_research_gap(
            state,
            ResearchGapTarget(
                ResearchGapTargetKind.IDENTITY, identity.resolution_ref
            ),
            ResearchGapReason.PROVISIONAL_IDENTITY,
            self.t1,
            gap_ref="gap:explicit",
            basis_refs=(identity.resolution_ref,),
            identity_resolutions=(identity,),
            trigger_ref="need:firm-identity",
        )
        self.assertIs(gap.reason, ResearchGapReason.PROVISIONAL_IDENTITY)

    def test_revalidation_is_explicit_stale_is_not_false_and_no_scheduler_exists(self):
        proposition = self.proposition("price", "50")
        trace = self.assessment(
            "assessment:price", proposition, AssessmentStatus.ESTABLISHED, self.t1
        )
        completeness = build_knowledge_completeness(
            self.reality,
            self.t1,
            facets=(
                KnowledgeFacetState(
                    "price",
                    KnowledgeFacetStatus.KNOWN,
                    self.t1,
                    (proposition.fingerprint,),
                    (trace.assessment_ref,),
                ),
            ),
        )
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:price",
            completeness=completeness,
            assessment_traces=(trace,),
            lineage_assessment_refs=(trace.assessment_ref,),
        )
        need = build_revalidation_need(
            state,
            proposition.fingerprint,
            RevalidationReason.REVALIDATION_DUE,
            self.t2,
            need_ref="revalidation:price",
            basis_ref=trace.assessment_ref,
            due_at=self.t2,
            revalidation_rule_ref="rule:price",
            revalidation_rule_version="1",
        )
        self.assertIs(validate_revalidation_need(state, need), need)
        self.assertIs(trace.assessment.status, AssessmentStatus.ESTABLISHED)
        self.assertNotIn(need.reason.value, ("FALSE", "CONTRADICTORY", "UNKNOWN"))
        gap = build_research_gap(
            state,
            ResearchGapTarget(
                ResearchGapTargetKind.PROPOSITION, proposition.fingerprint
            ),
            ResearchGapReason.REVALIDATION_DUE,
            self.t2,
            gap_ref="gap:revalidate",
            basis_refs=(need.need_ref,),
            revalidation_needs=(need,),
            revalidation_due_at=need.due_at,
        )
        for forbidden in ("scheduler", "provider", "research_mission", "priority_score"):
            self.assertFalse(hasattr(gap, forbidden))

    def test_assessed_at_alone_never_creates_due_at_and_rule_version_needs_rule(self):
        state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:freshness",
            completeness=self.unknown_completeness(),
        )
        need = build_revalidation_need(
            state,
            "deadline",
            RevalidationReason.EXPLICIT_REQUEST,
            self.t1,
            need_ref="revalidation:explicit",
            basis_ref="deadline",
        )
        self.assertIsNone(need.due_at)
        with self.assertRaises(MayeleContractError):
            build_revalidation_need(
                state,
                "deadline",
                RevalidationReason.REVALIDATION_DUE,
                self.t1,
                need_ref="revalidation:bad",
                basis_ref="deadline",
                revalidation_rule_version="2",
            )

    def test_unresolved_assessment_gap_cannot_resolve_while_cause_remains(self):
        proposition = self.proposition("deadline", "unknown")
        assessment = self.assessment(
            "assessment:still-unresolved",
            proposition,
            AssessmentStatus.UNRESOLVED,
            self.t1,
        )
        old_state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:unresolved-old",
            completeness=self.unknown_completeness(),
            assessment_traces=(assessment,),
            lineage_assessment_refs=(assessment.assessment_ref,),
        )
        gap = build_research_gap(
            old_state,
            ResearchGapTarget(
                ResearchGapTargetKind.PROPOSITION, proposition.fingerprint
            ),
            ResearchGapReason.UNRESOLVED_ASSESSMENT,
            self.t1,
            gap_ref="gap:still-unresolved",
            basis_refs=(assessment.assessment_ref,),
            assessment_traces=(assessment,),
        )
        new_state = build_knowledge_state(
            self.reality,
            self.t2,
            state_ref="state:unresolved-new",
            completeness=self.unknown_completeness(at=self.t2),
            assessment_traces=(assessment,),
            lineage_assessment_refs=(assessment.assessment_ref,),
        )
        with self.assertRaises(MayeleContractError):
            resolve_research_gap(
                gap,
                new_state,
                self.t2,
                assessment_traces=(assessment,),
            )

    def test_new_state_can_resolve_old_gap_without_mutating_history(self):
        old_state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:old",
            completeness=self.unknown_completeness(),
        )
        gap = build_research_gap(
            old_state,
            ResearchGapTarget(ResearchGapTargetKind.FACET, "deadline"),
            ResearchGapReason.UNKNOWN,
            self.t1,
            gap_ref="gap:old",
            basis_refs=("deadline",),
            trigger_ref="need:deadline",
        )
        proposition = self.proposition("deadline", "2027-01-15")
        trace = self.assessment(
            "assessment:new", proposition, AssessmentStatus.ESTABLISHED, self.t2
        )
        new_state = build_knowledge_state(
            self.reality,
            self.t2,
            state_ref="state:new",
            completeness=build_knowledge_completeness(
                self.reality,
                self.t2,
                facets=(
                    KnowledgeFacetState(
                        "deadline",
                        KnowledgeFacetStatus.KNOWN,
                        self.t2,
                        (proposition.fingerprint,),
                        (trace.assessment_ref,),
                    ),
                ),
            ),
            assessment_traces=(trace,),
            lineage_assessment_refs=(trace.assessment_ref,),
        )
        resolution = resolve_research_gap(gap, new_state, self.t2)
        self.assertIs(
            resolution.resolution_kind, ResearchGapResolutionKind.RESOLVED
        )
        self.assertIs(
            old_state.completeness.facet("deadline").status,
            KnowledgeFacetStatus.UNKNOWN,
        )
        self.assertIs(
            new_state.completeness.facet("deadline").status,
            KnowledgeFacetStatus.KNOWN,
        )

    def test_private_scope_is_preserved_by_state_gap_revalidation_and_resolution(self):
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        old_state = build_knowledge_state(
            self.reality,
            self.t1,
            state_ref="state:private",
            completeness=self.unknown_completeness(scope=private),
        )
        gap = build_research_gap(
            old_state,
            ResearchGapTarget(ResearchGapTargetKind.FACET, "deadline"),
            ResearchGapReason.UNKNOWN,
            self.t1,
            gap_ref="gap:private",
            basis_refs=("deadline",),
            trigger_ref="need:deadline",
        )
        need = build_revalidation_need(
            old_state,
            "deadline",
            RevalidationReason.EXPLICIT_REQUEST,
            self.t1,
            need_ref="revalidation:private",
            basis_ref="deadline",
        )
        self.assertEqual(gap.scope, private)
        self.assertEqual(need.scope, private)
        with self.assertRaises(MayeleContractError):
            build_research_gap(
                old_state,
                ResearchGapTarget(ResearchGapTargetKind.FACET, "deadline"),
                ResearchGapReason.UNKNOWN,
                self.t1,
                gap_ref="gap:widen",
                basis_refs=("deadline",),
                trigger_ref="need:deadline",
                scope=KnowledgeScope(),
            )

        new_public_state = build_knowledge_state(
            self.reality,
            self.t2,
            state_ref="state:public-new",
            completeness=build_knowledge_completeness(
                self.reality,
                self.t2,
                facets=(
                    KnowledgeFacetState(
                        "deadline",
                        KnowledgeFacetStatus.NOT_APPLICABLE,
                        self.t2,
                        applicability_basis_refs=("applicability:new",),
                    ),
                ),
            ),
        )
        resolution = resolve_research_gap(gap, new_public_state, self.t2)
        self.assertEqual(resolution.scope, private)
