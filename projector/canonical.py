from __future__ import annotations

from activities.projector_snapshots import (
    OccurrenceProjectorSnapshot,
    iter_occurrence_projector_ids,
    load_occurrence_projector_snapshot,
)

from .contracts import stable_fingerprint
from .exceptions import MissingCanonicalDependency


def load_occurrence_snapshot(occurrence_id) -> OccurrenceProjectorSnapshot:
    snapshot = load_occurrence_projector_snapshot(occurrence_id)
    if snapshot is None:
        raise MissingCanonicalDependency(
            "Occurrence canonique introuvable. Une suppression technique n'est pas "
            "interprétée comme une disparition Univers."
        )
    return snapshot


def occurrence_projection_ids():
    return tuple(iter_occurrence_projector_ids())


def occurrence_semantic_fingerprint(source: OccurrenceProjectorSnapshot) -> str:
    return stable_fingerprint(
        {
            "occurrence_id": source.occurrence_id,
            "activity_id": source.activity_id,
            "status": source.status,
            "timing_kind": source.timing_kind,
            "start_date": source.start_date,
            "start_time": source.start_time,
            "end_date": source.end_date,
            "end_time": source.end_time,
            "timezone": source.timezone,
        }
    )
