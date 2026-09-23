from __future__ import annotations

from .canonical import load_occurrence_snapshot, occurrence_projection_ids
from .contracts import (
    PROJECTOR_SCOPE_REF,
    PROJECTOR_STRATEGY_VERSION,
    ProjectionChangeSignal,
    UniverseDelta,
    UniverseSnapshot,
    stable_fingerprint,
)
from .exceptions import UnsupportedProjectionFact
from .mapping import build_occurrence_projection
from .ports import UniverseProjectionPort


def build_full_snapshot() -> UniverseSnapshot:
    roots = tuple(
        build_occurrence_projection(load_occurrence_snapshot(occurrence_id))
        for occurrence_id in occurrence_projection_ids()
    )
    roots = tuple(sorted(roots, key=lambda root: root.projection_ref))
    fingerprint = stable_fingerprint(
        {
            "scope_ref": PROJECTOR_SCOPE_REF,
            "strategy_version": PROJECTOR_STRATEGY_VERSION,
            "roots": tuple(root.semantic_fingerprint for root in roots),
        }
    )
    return UniverseSnapshot(
        scope_ref=PROJECTOR_SCOPE_REF,
        strategy_version=PROJECTOR_STRATEGY_VERSION,
        roots=roots,
        semantic_fingerprint=fingerprint,
    )


def build_delta(change: ProjectionChangeSignal) -> UniverseDelta:
    if change.fact_kind != "occurrence":
        raise UnsupportedProjectionFact(
            f"Actor 7 ne projette pas encore le fait {change.fact_kind!r}."
        )
    root = build_occurrence_projection(load_occurrence_snapshot(change.fact_id))
    return UniverseDelta(
        scope_ref=PROJECTOR_SCOPE_REF,
        strategy_version=PROJECTOR_STRATEGY_VERSION,
        change_ref=change.change_ref,
        upserts=(root,),
    )


def project_full_snapshot(*, port: UniverseProjectionPort) -> UniverseSnapshot:
    snapshot = build_full_snapshot()
    port.apply_snapshot(snapshot)
    return snapshot


def project_change(*, change: ProjectionChangeSignal, port: UniverseProjectionPort) -> UniverseDelta:
    delta = build_delta(change)
    port.apply_delta(delta)
    return delta
