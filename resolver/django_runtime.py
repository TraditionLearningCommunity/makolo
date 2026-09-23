from __future__ import annotations

from .django_store import (
    claim_resolutions,
    enqueue_resolutions,
    process_resolution_claim,
    recover_expired_resolutions,
    report_pending_feedback,
)
from .strategy import DeterministicResolver


def run_resolver_cycle(*, worker_id, batch_size=20, lease_seconds=300, interpretation_ref=None):
    strategy = DeterministicResolver()
    recovered = recover_expired_resolutions()
    enqueued = enqueue_resolutions(
        strategy=strategy,
        limit=max(batch_size * 4, 20),
        interpretation_ref=interpretation_ref,
    )
    claims = claim_resolutions(
        worker_id=worker_id,
        limit=batch_size,
        lease_seconds=lease_seconds,
    )
    stats = {
        "recovered": recovered,
        "enqueued": enqueued,
        "claimed": len(claims),
        "finalized": 0,
        "failed": 0,
        "assertions": 0,
    }
    for claim in claims:
        run = process_resolution_claim(claim, strategy=strategy)
        stats["finalized"] += int(run.lifecycle == "finalized")
        stats["failed"] += int(run.outcome == "failed")
        stats["assertions"] += int((run.stats or {}).get("assertion_count", 0))
    feedback = report_pending_feedback(limit=max(batch_size * 4, 20))
    stats["feedback_reported"] = feedback["reported"]
    stats["feedback_failed"] = feedback["failed"]
    return stats
