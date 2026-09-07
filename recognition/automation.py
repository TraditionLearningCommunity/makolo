from __future__ import annotations

from django.utils import timezone

from .services import (
    complete_window,
    ensure_cursor,
    get_due_window,
    mark_window_running,
    process_impact_slice,
)


def run_recognition_cycle(
    *,
    slice_provider,
    policy,
    now=None,
    cursor_key: str = "network-utility",
    window_size_hours: int = 24,
):
    """Run at most one due Recognition window using injected domain adapters.

    The canonical Makolo scheduler may call this function frequently. The
    cursor decides whether a 24h (or configured) window is actually due, so
    cron frequency never changes the amount of Points granted.

    This function is intentionally not wired into ``automation.scheduler``
    until real domain adapters are selected. A no-op provider must not advance
    production watermarks and silently discard future backfill opportunities.
    """

    now = now or timezone.now()
    cursor = ensure_cursor(
        key=cursor_key,
        policy_version=policy.version,
        window_size_hours=window_size_hours,
        start_at=now,
    )
    window = get_due_window(cursor=cursor, now=now)
    if window is None:
        return {"due": False, "processed_slices": 0, "issued_points": 0, "initialized_at": cursor.last_completed_end}

    mark_window_running(window)
    created_count = 0
    # The provider must select facts by when they became available to Recognition
    # within [starts_at, ends_at), while preserving their real ``occurred_at``.
    # This lets late-arriving facts enter a later evaluation window safely.
    for candidate in slice_provider(window.starts_at, window.ends_at):
        result = process_impact_slice(
            window=window,
            slice_key=candidate.slice_key,
            accrual_key=candidate.accrual_key,
            channel=candidate.channel.value,
            temporal_profile=candidate.temporal_profile.value,
            occurred_at=candidate.occurred_at,
            available_at=candidate.available_at,
            impact_delta=candidate.impact_delta,
            attribution_shares=candidate.attribution_shares,
            points_target_for_cumulative=policy.target_points,
            policy_version=policy.version,
            metadata=candidate.metadata,
        )
        created_count += int(result.created)
    window = complete_window(window=window, cursor=cursor)
    return {
        "due": True,
        "window": {"starts_at": window.starts_at, "ends_at": window.ends_at},
        "processed_slices": created_count,
        "issued_points": window.issued_points,
        "unattributed_points": window.unattributed_points,
        "pool_points": window.pool_points,
    }
