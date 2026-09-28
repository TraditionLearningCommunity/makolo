from __future__ import annotations

from datetime import timedelta

from opportunities.models import (
    OpportunitySource,
    OpportunitySourceCheckResult,
    OpportunitySourceStatus,
)
from prospector.canonicalization import canonicalize_web_url

from .discovery import DiscoveryKnownRef
from .watch import (
    FreshnessPolicy,
    WatchChangeState,
    WatchFreshnessState,
    WatchLookup,
)


MAX_SOURCE_SCAN = 100


def _canonical(value: str) -> str | None:
    try:
        return canonicalize_web_url(value)
    except Exception:
        return None


_STATUS_TO_CHANGE = {
    OpportunitySourceStatus.ACTIVE: WatchChangeState.UNKNOWN,
    OpportunitySourceStatus.CHANGED: WatchChangeState.CHANGED,
    OpportunitySourceStatus.UNREACHABLE: WatchChangeState.UNREACHABLE,
    OpportunitySourceStatus.REMOVED: WatchChangeState.REMOVED,
}

_CHECK_TO_CHANGE = {
    OpportunitySourceCheckResult.UNCHANGED: WatchChangeState.UNCHANGED,
    OpportunitySourceCheckResult.CHANGED: WatchChangeState.CHANGED,
    OpportunitySourceCheckResult.UNREACHABLE: WatchChangeState.UNREACHABLE,
    OpportunitySourceCheckResult.REMOVED: WatchChangeState.REMOVED,
}


class DjangoWatchKnowledgeCatalog:
    """Read-only freshness adapter for known Opportunity sources.

    It reuses canonical OpportunitySource/OpportunitySourceCheck history. It
    never records a check itself and never mutates source status.
    """

    def assess(self, *, source, now, policy: FreshnessPolicy):
        canonical = _canonical(source.locator)
        if canonical is None:
            return WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=("invalid_source_locator",),
            )

        matches = []
        for row in (
            OpportunitySource.objects.select_related("opportunity")
            .order_by("id")[:MAX_SOURCE_SCAN]
        ):
            if _canonical(row.url) == canonical:
                matches.append(row)

        if len(matches) != 1:
            return WatchLookup(
                freshness_state=WatchFreshnessState.UNRESOLVED,
                basis_codes=(
                    "source_not_known"
                    if not matches
                    else "source_matches_multiple_known_rows",
                ),
            )

        row = matches[0]
        known_ref = DiscoveryKnownRef(
            domain="opportunity",
            object_ref=str(row.opportunity_id),
        )

        last_check = row.checks.order_by("-checked_at", "-created_at", "-id").first()
        if last_check is not None:
            last_change_state = _CHECK_TO_CHANGE.get(
                last_check.result,
                WatchChangeState.UNKNOWN,
            )
        else:
            last_change_state = _STATUS_TO_CHANGE.get(
                row.status,
                WatchChangeState.UNKNOWN,
            )

        if row.last_checked_at is None:
            return WatchLookup(
                freshness_state=WatchFreshnessState.DUE,
                known_ref=known_ref,
                last_checked_at=None,
                due_at=now,
                last_change_state=last_change_state,
                basis_codes=("known_source_never_checked",),
            )

        due_at = row.last_checked_at + policy.max_age
        freshness_state = (
            WatchFreshnessState.DUE
            if due_at <= now
            else WatchFreshnessState.FRESH
        )
        return WatchLookup(
            freshness_state=freshness_state,
            known_ref=known_ref,
            last_checked_at=row.last_checked_at,
            due_at=due_at,
            last_change_state=last_change_state,
            basis_codes=(
                "freshness_window_elapsed"
                if freshness_state is WatchFreshnessState.DUE
                else "within_freshness_window",
            ),
        )
