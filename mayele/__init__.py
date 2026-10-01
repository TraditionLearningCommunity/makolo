"""Autonomous Mayele knowledge subsystem.

MY1 deliberately exposes only framework-independent semantic contracts.
"""

from .knowledge.contracts import (
    Condition,
    KnowledgeSupport,
    Property,
    Proposition,
    PropositionAssessment,
    Reality,
    Relation,
)

__all__ = [
    "Condition",
    "KnowledgeSupport",
    "Property",
    "Proposition",
    "PropositionAssessment",
    "Reality",
    "Relation",
]
