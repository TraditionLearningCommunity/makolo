from __future__ import annotations

from intelligence.capabilities import IntelligenceCapability
from intelligence.gateway import IntelligenceGateway
from intelligence.runtime import build_runtime_registry

from .contracts import strategy_fingerprint
from .django_store import (
    claim_interpretations,
    enqueue_interpretations,
    process_interpretation_claim,
    recover_expired_interpretations,
    report_pending_feedback,
)
from .extraction import DeterministicInterpreter, STRATEGY_COMPONENTS
from .intelligence_enrichment import IntelligenceCandidateExtractor


def _runtime_strategy():
    registry = build_runtime_registry(
        capability=IntelligenceCapability.STRUCTURED_GENERATE,
    )
    providers = registry.providers_for(IntelligenceCapability.STRUCTURED_GENERATE)
    route_signature = "|".join(
        f"{index}:{provider.__class__.__name__}:{getattr(provider, 'key', '')}:{getattr(provider, 'model', '')}"
        for index, provider in enumerate(providers)
    )
    fingerprint = None
    if route_signature:
        fingerprint = strategy_fingerprint(
            {**STRATEGY_COMPONENTS, "intelligence_route": route_signature}
        )
    return DeterministicInterpreter(
        intelligence_extractor=IntelligenceCandidateExtractor(
            IntelligenceGateway(registry=registry)
        ),
        strategy_fingerprint_override=fingerprint,
    )


def run_interpreter_cycle(*, worker_id, batch_size=20, lease_seconds=300, observation_ref=None):
    strategy = _runtime_strategy()
    recovered = recover_expired_interpretations()
    enqueued = enqueue_interpretations(
        strategy=strategy,
        limit=max(batch_size * 4, 20),
        observation_ref=observation_ref,
    )
    claims = claim_interpretations(
        worker_id=worker_id,
        limit=batch_size,
        lease_seconds=lease_seconds,
        strategy_fingerprint=strategy.strategy_fingerprint,
    )
    stats = {
        "recovered": recovered,
        "enqueued": enqueued,
        "claimed": len(claims),
        "finalized": 0,
        "failed": 0,
        "candidates": 0,
        "intelligence_calls": 0,
        "intelligence_candidates_accepted": 0,
        "intelligence_candidates_rejected": 0,
    }
    for claim in claims:
        run = process_interpretation_claim(claim, strategy=strategy)
        stats["finalized"] += 1
        stats["failed"] += int(run.outcome == "failed")
        stats["candidates"] += int((run.stats or {}).get("candidate_count", 0))
        stats["intelligence_calls"] += int((run.stats or {}).get("intelligence_calls", 0))
        stats["intelligence_candidates_accepted"] += int(
            (run.stats or {}).get("intelligence_candidates_accepted", 0)
        )
        stats["intelligence_candidates_rejected"] += int(
            (run.stats or {}).get("intelligence_candidates_rejected", 0)
        )
    feedback = report_pending_feedback(limit=max(batch_size * 4, 20))
    stats["feedback_reported"] = feedback["reported"]
    stats["feedback_failed"] = feedback["failed"]
    return stats
