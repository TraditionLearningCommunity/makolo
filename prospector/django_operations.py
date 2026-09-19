from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone

from django.db import connection
from django.db.models import Count, Max, Min, Q

from prospector.errors import ProspectorContractError
from prospector.frontier import FrontierState
from prospector.operations import OperationsSnapshot

from .django_app.models import (
    ProspectorBudgetCounter,
    ProspectorBudgetReservation,
    ProspectorFeedbackEvent,
    ProspectorFeedbackProjection,
    ProspectorFrontierEntry,
    ProspectorFrontierEvidence,
    ProspectorSourceCheckpoint,
)


def _aware(name: str, value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(dt_timezone.utc)


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    seconds = int((now - value).total_seconds())
    return max(seconds, 0)


class DjangoOperationsReader:
    """Aggregate operational telemetry with no locators, content or PII."""

    def snapshot_sync(self, *, now: datetime) -> OperationsSnapshot:
        now = _aware("now", now)
        entries = ProspectorFrontierEntry.objects.all()
        ready_due = entries.filter(
            status=FrontierState.READY.value,
            available_at__lte=now,
        )
        claimed = entries.filter(status=FrontierState.CLAIMED.value)
        stale_claims = claimed.filter(lease_expires_at__lte=now)

        counts = {
            row["status"]: row["total"]
            for row in entries.values("status").annotate(total=Count("id"))
        }
        suppression_reasons = {
            row["suppression_reason"]: row["total"]
            for row in entries.filter(
                status=FrontierState.SUPPRESSED.value
            )
            .exclude(suppression_reason="")
            .values("suppression_reason")
            .annotate(total=Count("id"))
        }

        oldest_ready = ready_due.aggregate(value=Min("available_at"))["value"]
        checkpoints = ProspectorSourceCheckpoint.objects.all()
        active_checkpoints = checkpoints.filter(exhausted=False)
        oldest_checkpoint = active_checkpoints.aggregate(
            value=Min("checkpoint_updated_at")
        )["value"]

        projection_max_id = (
            ProspectorFeedbackProjection.objects.aggregate(
                value=Max("last_event_id")
            )["value"]
            or 0
        )
        # IDs are monotonic but not gap-free (rollbacks/deletes can consume
        # sequence values). Operational lag is the number of real events still
        # beyond the most advanced projection checkpoint, not an ID distance.
        feedback_lag = ProspectorFeedbackEvent.objects.filter(
            id__gt=projection_max_id
        ).count()

        return OperationsSnapshot(
            captured_at=now,
            frontier_total=entries.count(),
            ready_due=ready_due.count(),
            claimed=claimed.count(),
            stale_claims=stale_claims.count(),
            completed=int(counts.get(FrontierState.COMPLETED.value, 0)),
            suppressed=int(counts.get(FrontierState.SUPPRESSED.value, 0)),
            evidence_rows=ProspectorFrontierEvidence.objects.count(),
            source_checkpoints=checkpoints.count(),
            active_source_checkpoints=active_checkpoints.count(),
            feedback_events=ProspectorFeedbackEvent.objects.count(),
            feedback_projections=ProspectorFeedbackProjection.objects.count(),
            feedback_projection_lag_events=feedback_lag,
            expired_budget_counters=ProspectorBudgetCounter.objects.filter(
                period_end__lt=now
            ).count(),
            expired_budget_reservations=ProspectorBudgetReservation.objects.filter(
                period_end__lt=now
            ).count(),
            oldest_ready_age_seconds=_age_seconds(now, oldest_ready),
            oldest_active_checkpoint_age_seconds=_age_seconds(
                now,
                oldest_checkpoint,
            ),
            suppression_reasons=suppression_reasons,
        )


class DjangoProspectorMaintenance:
    """Safe maintenance of rebuildable/expired operational state only."""

    def prune_expired_budgets_sync(
        self,
        *,
        before: datetime,
        apply: bool,
    ) -> dict:
        before = _aware("before", before)
        if not isinstance(apply, bool):
            raise ProspectorContractError("apply must be a boolean")

        counters = ProspectorBudgetCounter.objects.filter(period_end__lt=before)
        reservations = ProspectorBudgetReservation.objects.filter(
            period_end__lt=before
        )
        result = {
            "before": before.isoformat(),
            "apply": apply,
            "budget_counters": counters.count(),
            "budget_reservations": reservations.count(),
        }
        if apply:
            reservations.delete()
            counters.delete()
        return result

    def frontier_claim_plan_sync(self, *, now: datetime, limit: int) -> dict:
        now = _aware("now", now)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ProspectorContractError("limit must be a positive integer")
        if connection.vendor != "postgresql":
            raise ProspectorContractError(
                "frontier query-plan inspection requires PostgreSQL"
            )

        queryset = (
            ProspectorFrontierEntry.objects.filter(
                Q(
                    status=FrontierState.READY.value,
                    available_at__lte=now,
                )
                | Q(
                    status=FrontierState.CLAIMED.value,
                    lease_expires_at__lte=now,
                )
            )
            .order_by("priority", "available_at", "id")
            .values("id")[:limit]
        )
        raw = queryset.explain(format="json")
        try:
            explained = json.loads(raw)
            plan = explained[0]["Plan"]
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise ProspectorContractError(
                "PostgreSQL returned an invalid EXPLAIN JSON payload"
            ) from exc
        return {
            "database": "postgresql",
            "limit": limit,
            "node_type": plan.get("Node Type"),
            "startup_cost": plan.get("Startup Cost"),
            "total_cost": plan.get("Total Cost"),
            "plan_rows": plan.get("Plan Rows"),
            "plan_width": plan.get("Plan Width"),
        }
