from __future__ import annotations

from django.db.models import Count, Sum

from prospector.feedback import FeedbackSignal
from prospector.pilot import PilotSnapshot

from .django_app.models import (
    ProspectorFeedbackEvent,
    ProspectorFrontierEntry,
    ProspectorFrontierEvidence,
)


def _count_map(queryset, field: str) -> dict[str, int]:
    rows = queryset.values(field).annotate(total=Count("id")).order_by(field)
    return {
        str(row[field]): int(row["total"])
        for row in rows
        if row[field] not in {None, ""}
    }


class DjangoPilotSnapshotReader:
    """Read-only PX8 scorecard projection scoped to one mission fingerprint."""

    def snapshot_sync(self, *, mission_fingerprint: str) -> PilotSnapshot:
        entries = ProspectorFrontierEntry.objects.filter(
            policy_context__mission_fingerprint=mission_fingerprint
        )
        aggregate = entries.aggregate(total_discoveries=Sum("discovery_count"))
        evidence = ProspectorFrontierEvidence.objects.filter(
            frontier_entry__in=entries
        )
        target_keys = list(entries.values_list("target_key", flat=True))
        feedback = ProspectorFeedbackEvent.objects.filter(
            target_key__in=target_keys
        )

        return PilotSnapshot(
            entry_count=entries.count(),
            discovery_count=int(aggregate["total_discoveries"] or 0),
            evidence_count=evidence.count(),
            feedback_events=feedback.count(),
            statuses=_count_map(entries, "status"),
            suppression_reasons=_count_map(entries, "suppression_reason"),
            feedback_signals=_count_map(feedback, "signal"),
            evidence_methods=_count_map(evidence, "method"),
            providers=_count_map(evidence, "provider"),
        )
