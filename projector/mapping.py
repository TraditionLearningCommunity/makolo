from __future__ import annotations

from activities.models import OccurrenceStatus, OccurrenceTimingKind
from activities.projector_snapshots import OccurrenceProjectorSnapshot

from .canonical import occurrence_semantic_fingerprint
from .contracts import (
    PROJECTOR_STRATEGY_VERSION,
    CanonicalFactRef,
    ProjectedValue,
    UniversePlan,
    UniverseProjectionRoot,
    UniverseTemporalDeclaration,
    ValueState,
    stable_fingerprint,
)
from .exceptions import InconsistentCanonicalState


_PLAN_LIFECYCLE = {
    OccurrenceStatus.DRAFT: "declared",
    OccurrenceStatus.SCHEDULED: "scheduled",
    OccurrenceStatus.CANCELLED: "cancelled",
    OccurrenceStatus.COMPLETED: "closed",
}


def _known_or_unknown(value):
    if value is None:
        return ProjectedValue(ValueState.UNKNOWN)
    return ProjectedValue(ValueState.KNOWN, str(value))


def _time_value(value, *, timing_kind):
    if timing_kind == OccurrenceTimingKind.ALL_DAY:
        return ProjectedValue(ValueState.NOT_APPLICABLE)
    return _known_or_unknown(value)


def build_occurrence_projection(source: OccurrenceProjectorSnapshot) -> UniverseProjectionRoot:
    try:
        lifecycle = _PLAN_LIFECYCLE[source.status]
    except KeyError as exc:
        raise InconsistentCanonicalState(
            f"Statut Occurrence non projetable: {source.status!r}."
        ) from exc

    activity_fact = CanonicalFactRef(
        kind="activity",
        fact_id=source.activity_id,
        fingerprint=stable_fingerprint({"activity_id": source.activity_id}),
    )
    occurrence_fact = CanonicalFactRef(
        kind="occurrence",
        fact_id=source.occurrence_id,
        fingerprint=occurrence_semantic_fingerprint(source),
    )
    temporal = UniverseTemporalDeclaration(
        timing_kind=source.timing_kind,
        start_date=_known_or_unknown(source.start_date),
        start_time=_time_value(source.start_time, timing_kind=source.timing_kind),
        end_date=_known_or_unknown(source.end_date),
        end_time=_time_value(source.end_time, timing_kind=source.timing_kind),
        timezone=_known_or_unknown(source.timezone or None),
    )
    plan = UniversePlan(
        ref=f"declared-realization:{source.occurrence_id}",
        kind="declared_realization_plan",
        lifecycle=lifecycle,
        temporal=temporal,
    )
    semantic = {
        "projection_ref": f"occurrence-plan:{source.occurrence_id}",
        "projection_kind": "declared_realization_plan",
        "strategy_version": PROJECTOR_STRATEGY_VERSION,
        "source_facts": (activity_fact, occurrence_fact),
        "plans": (plan,),
        "bodies": (),
        "relations": (),
        "conditions": (),
        "states": (),
        "parameters": (),
    }
    return UniverseProjectionRoot(
        **semantic,
        source_revision=source.source_revision,
        semantic_fingerprint=stable_fingerprint(semantic),
    )
