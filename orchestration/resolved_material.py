from __future__ import annotations

import logging
from typing import Callable

from resolver.contracts import (
    AssertionKind,
    EndpointKind,
    ResolvedMaterial,
    ResolutionOutcome,
    ResolutionStatus,
)

from .contracts import (
    OrchestrationContext,
    OrchestrationDecision,
    OrchestrationDecisionRecord,
    OrchestrationResult,
    OwnerDecision,
)

logger = logging.getLogger(__name__)


class ResolvedMaterialOwnerRegistry:
    """Explicit owner adapters only; no dynamic model or field dispatch."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, domain: str, handler: Callable):
        domain = str(domain or "").strip().lower()
        if not domain:
            raise ValueError("owner domain must not be empty")
        if not callable(handler):
            raise ValueError("owner handler must be callable")
        if domain in self._handlers and self._handlers[domain] is not handler:
            raise ValueError(f"owner domain {domain!r} is already registered")
        self._handlers[domain] = handler
        return handler

    def get(self, domain: str):
        return self._handlers.get(domain)


def build_default_resolved_material_registry() -> ResolvedMaterialOwnerRegistry:
    from .activity_owner import ActivityResolvedMaterialHandler

    registry = ResolvedMaterialOwnerRegistry()
    registry.register("activity", ActivityResolvedMaterialHandler())
    return registry


def _canonical_ref(assertion):
    if assertion.canonical_ref is not None:
        return assertion.canonical_ref
    if (
        assertion.subject is not None
        and assertion.subject.kind is EndpointKind.CANONICAL
        and assertion.subject.canonical_ref is not None
    ):
        return assertion.subject.canonical_ref
    return None


def _record(
    material,
    assertion,
    decision,
    reason_code,
    *,
    owner_domain=None,
    operation=None,
    applied_ref=None,
):
    canonical = _canonical_ref(assertion)
    record = OrchestrationDecisionRecord(
        resolution_ref=material.resolution_ref,
        assertion_ref=assertion.assertion_ref,
        decision=decision,
        reason_code=reason_code,
        owner_domain=owner_domain,
        operation=operation,
        canonical_object_ref=canonical.object_ref if canonical else None,
        applied_ref=applied_ref,
    )
    logger.info(
        "orchestrator.resolved_material.decision",
        extra={
            "resolution_ref": material.resolution_ref,
            "assertion_ref": assertion.assertion_ref,
            "decision": record.decision.value,
            "reason_code": reason_code,
            "owner_domain": owner_domain or "",
            "operation": operation or "",
        },
    )
    return record


def _pre_decision(material, assertion):
    if assertion.kind is AssertionKind.CONFLICT or assertion.status is ResolutionStatus.CONFLICT:
        return _record(
            material,
            assertion,
            OrchestrationDecision.CONFLICT,
            "resolved_conflict_requires_no_mutation",
        )
    if assertion.status is ResolutionStatus.REJECTED:
        return _record(
            material,
            assertion,
            OrchestrationDecision.REJECT,
            "resolver_rejected_assertion",
        )
    if assertion.status in {ResolutionStatus.AMBIGUOUS, ResolutionStatus.UNRESOLVED}:
        return _record(
            material,
            assertion,
            OrchestrationDecision.DEFER,
            f"resolver_{assertion.status.value}",
        )
    if assertion.status is ResolutionStatus.PARTIAL:
        return _record(
            material,
            assertion,
            OrchestrationDecision.DEFER,
            "partial_resolution",
        )
    if assertion.status is ResolutionStatus.NEW_CANDIDATE:
        return _record(
            material,
            assertion,
            OrchestrationDecision.REVIEW,
            "new_candidate_requires_owner_decision",
        )
    if assertion.kind is AssertionKind.ENTITY and assertion.status is ResolutionStatus.MATCHED:
        canonical = _canonical_ref(assertion)
        return _record(
            material,
            assertion,
            OrchestrationDecision.NO_ACTION,
            "identity_match_is_not_a_business_mutation",
            owner_domain=canonical.domain if canonical else None,
        )
    return None


def orchestrate_resolved_material(
    material: ResolvedMaterial,
    *,
    context: OrchestrationContext | None = None,
    registry: ResolvedMaterialOwnerRegistry | None = None,
) -> OrchestrationResult:
    if not isinstance(material, ResolvedMaterial):
        raise TypeError("material must be ResolvedMaterial v1")
    if material.contract_version != 1:
        raise ValueError("unsupported ResolvedMaterial contract version")

    context = context or OrchestrationContext()
    registry = registry or build_default_resolved_material_registry()

    if material.outcome is ResolutionOutcome.FAILED:
        logger.warning(
            "orchestrator.resolved_material.failed",
            extra={"resolution_ref": material.resolution_ref},
        )
        return OrchestrationResult(
            resolution_ref=material.resolution_ref,
            source_outcome=material.outcome.value,
            decisions=(),
        )

    decisions = []
    for assertion in material.assertions:
        pre_decision = _pre_decision(material, assertion)
        if pre_decision is not None:
            decisions.append(pre_decision)
            continue

        canonical = _canonical_ref(assertion)
        if canonical is None:
            decisions.append(
                _record(
                    material,
                    assertion,
                    OrchestrationDecision.DEFER,
                    "canonical_owner_not_resolved",
                )
            )
            continue

        handler = registry.get(canonical.domain)
        if handler is None:
            decisions.append(
                _record(
                    material,
                    assertion,
                    OrchestrationDecision.REVIEW,
                    "owner_handler_not_registered",
                    owner_domain=canonical.domain,
                )
            )
            continue

        owner_decision: OwnerDecision = handler(
            material=material,
            assertion=assertion,
            context=context,
        )
        decisions.append(
            _record(
                material,
                assertion,
                owner_decision.decision,
                owner_decision.reason_code,
                owner_domain=canonical.domain,
                operation=owner_decision.operation,
                applied_ref=owner_decision.applied_ref,
            )
        )

    return OrchestrationResult(
        resolution_ref=material.resolution_ref,
        source_outcome=material.outcome.value,
        decisions=tuple(decisions),
    )


def orchestrate_resolution(
    resolution_ref: str,
    *,
    source,
    context: OrchestrationContext | None = None,
    registry: ResolvedMaterialOwnerRegistry | None = None,
) -> OrchestrationResult:
    """Consume the Actor-4 port without importing Resolver ORM state."""

    material = source.get_material(resolution_ref)
    return orchestrate_resolved_material(
        material,
        context=context,
        registry=registry,
    )
