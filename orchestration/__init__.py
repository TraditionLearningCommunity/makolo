"""Actor 5 application-orchestration contracts.

This package is intentionally small. Canonical business rules, transactions and
persistence remain owned by their domain services.
"""

from .contracts import (
    OrchestrationContext,
    OrchestrationDecision,
    OrchestrationDecisionRecord,
    OrchestrationResult,
    OrchestrationTrigger,
    OwnerDecision,
)
from .resolved_material import (
    ResolvedMaterialOwnerRegistry,
    build_default_resolved_material_registry,
    orchestrate_resolved_material,
    orchestrate_resolution,
)

__all__ = [
    "OrchestrationContext",
    "OrchestrationDecision",
    "OrchestrationDecisionRecord",
    "OrchestrationResult",
    "OrchestrationTrigger",
    "OwnerDecision",
    "ResolvedMaterialOwnerRegistry",
    "build_default_resolved_material_registry",
    "orchestrate_resolved_material",
    "orchestrate_resolution",
]
