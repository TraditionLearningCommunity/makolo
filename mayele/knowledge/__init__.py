"""Mayele Knowledge semantic core."""

from .semantics import KnowledgeValue
from .contracts import (
    AssessmentStatus,
    Condition,
    KnowledgeSupport,
    Property,
    Proposition,
    PropositionAssessment,
    PropositionKind,
    Reality,
    Relation,
    RelationParticipant,
    SupportDisposition,
    TemporalValidity,
)
from .construction import (
    KnowledgeSupportTrace,
    PropositionConstruction,
    build_knowledge_support,
    build_proposition_construction,
)
from .assessment import (
    PropositionAssessmentTrace,
    PropositionComparison,
    PropositionComparisonStatus,
    build_proposition_assessment,
)
from .assessment_gate import (
    validate_assessment_history,
    validate_proposition_assessment,
)

__all__ = [
    "AssessmentStatus",
    "Condition",
    "KnowledgeSupport",
    "KnowledgeSupportTrace",
    "KnowledgeValue",
    "Property",
    "Proposition",
    "PropositionAssessment",
    "PropositionAssessmentTrace",
    "PropositionComparison",
    "PropositionComparisonStatus",
    "PropositionConstruction",
    "PropositionKind",
    "Reality",
    "Relation",
    "RelationParticipant",
    "SupportDisposition",
    "TemporalValidity",
    "build_knowledge_support",
    "build_proposition_assessment",
    "build_proposition_construction",
    "validate_assessment_history",
    "validate_proposition_assessment",
]

from .completeness import (
    KnowledgeCompleteness,
    KnowledgeFacetState,
    KnowledgeFacetStatus,
    build_knowledge_completeness,
    validate_knowledge_completeness,
)
from .state import KnowledgeState, build_knowledge_state, validate_knowledge_state
from .gaps import (
    ResearchGap,
    ResearchGapReason,
    ResearchGapResolution,
    ResearchGapResolutionKind,
    ResearchGapTarget,
    ResearchGapTargetKind,
    RevalidationNeed,
    RevalidationReason,
    build_research_gap,
    build_revalidation_need,
    resolve_research_gap,
    validate_research_gap,
    validate_revalidation_need,
)

__all__.extend([
    "KnowledgeCompleteness",
    "KnowledgeFacetState",
    "KnowledgeFacetStatus",
    "KnowledgeState",
    "ResearchGap",
    "ResearchGapReason",
    "ResearchGapResolution",
    "ResearchGapResolutionKind",
    "ResearchGapTarget",
    "ResearchGapTargetKind",
    "RevalidationNeed",
    "RevalidationReason",
    "build_knowledge_completeness",
    "build_knowledge_state",
    "build_research_gap",
    "build_revalidation_need",
    "resolve_research_gap",
    "validate_knowledge_completeness",
    "validate_knowledge_state",
    "validate_research_gap",
    "validate_revalidation_need",
])
