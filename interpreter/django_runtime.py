from __future__ import annotations

from .django_store import claim_interpretations, enqueue_interpretations, process_interpretation_claim, recover_expired_interpretations, report_pending_feedback
from .extraction import DeterministicInterpreter


def run_interpreter_cycle(*, worker_id, batch_size=20, lease_seconds=300, observation_ref=None):
    strategy = DeterministicInterpreter()
    recovered = recover_expired_interpretations()
    enqueued = enqueue_interpretations(strategy=strategy, limit=max(batch_size * 4, 20), observation_ref=observation_ref)
    claims = claim_interpretations(worker_id=worker_id, limit=batch_size, lease_seconds=lease_seconds)
    stats = {"recovered": recovered, "enqueued": enqueued, "claimed": len(claims), "finalized": 0, "failed": 0, "candidates": 0}
    for claim in claims:
        run = process_interpretation_claim(claim, strategy=strategy)
        stats["finalized"] += 1
        stats["failed"] += int(run.outcome == "failed")
        stats["candidates"] += int((run.stats or {}).get("candidate_count", 0))
    feedback = report_pending_feedback(limit=max(batch_size * 4, 20))
    stats["feedback_reported"] = feedback["reported"]
    stats["feedback_failed"] = feedback["failed"]
    return stats
