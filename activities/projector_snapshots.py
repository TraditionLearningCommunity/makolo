from __future__ import annotations

from dataclasses import dataclass

from .models import Occurrence


@dataclass(frozen=True, slots=True)
class OccurrenceProjectorSnapshot:
    occurrence_id: str
    activity_id: str
    status: str
    timing_kind: str
    start_date: str | None
    start_time: str | None
    end_date: str | None
    end_time: str | None
    timezone: str
    source_revision: str


def _iso(value):
    return value.isoformat() if value is not None else None


def load_occurrence_projector_snapshot(occurrence_id) -> OccurrenceProjectorSnapshot | None:
    occurrence = (
        Occurrence.objects.only(
            "id",
            "activity_id",
            "status",
            "timing_kind",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "timezone",
            "updated_at",
        )
        .filter(pk=occurrence_id)
        .first()
    )
    if occurrence is None:
        return None
    return OccurrenceProjectorSnapshot(
        occurrence_id=str(occurrence.pk),
        activity_id=str(occurrence.activity_id),
        status=occurrence.status,
        timing_kind=occurrence.timing_kind,
        start_date=_iso(occurrence.start_date),
        start_time=_iso(occurrence.start_time),
        end_date=_iso(occurrence.end_date),
        end_time=_iso(occurrence.end_time),
        timezone=occurrence.timezone,
        source_revision=occurrence.updated_at.isoformat(),
    )


def iter_occurrence_projector_ids():
    yield from (
        str(pk)
        for pk in Occurrence.objects.order_by("id").values_list("id", flat=True).iterator()
    )
