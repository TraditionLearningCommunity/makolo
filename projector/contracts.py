from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any


PROJECTOR_STRATEGY_VERSION = "occurrence-plan-v1"
PROJECTOR_SCOPE_REF = "universe:declared-occurrence-plans"


class ValueState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ProjectedValue:
    state: ValueState
    value: str | None = None

    def __post_init__(self):
        if self.state == ValueState.KNOWN and self.value is None:
            raise ValueError("Une valeur KNOWN exige une valeur explicite.")
        if self.state != ValueState.KNOWN and self.value is not None:
            raise ValueError("UNKNOWN/NOT_APPLICABLE ne portent aucune valeur implicite.")


@dataclass(frozen=True, slots=True)
class CanonicalFactRef:
    kind: str
    fact_id: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class UniverseTemporalDeclaration:
    timing_kind: str
    start_date: ProjectedValue
    start_time: ProjectedValue
    end_date: ProjectedValue
    end_time: ProjectedValue
    timezone: ProjectedValue


@dataclass(frozen=True, slots=True)
class UniversePlan:
    ref: str
    kind: str
    lifecycle: str
    temporal: UniverseTemporalDeclaration


@dataclass(frozen=True, slots=True)
class UniverseProjectionRoot:
    projection_ref: str
    projection_kind: str
    strategy_version: str
    source_revision: str
    source_facts: tuple[CanonicalFactRef, ...]
    plans: tuple[UniversePlan, ...] = ()
    bodies: tuple[dict[str, Any], ...] = ()
    relations: tuple[dict[str, Any], ...] = ()
    conditions: tuple[dict[str, Any], ...] = ()
    states: tuple[dict[str, Any], ...] = ()
    parameters: tuple[dict[str, Any], ...] = ()
    semantic_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    scope_ref: str
    strategy_version: str
    roots: tuple[UniverseProjectionRoot, ...]
    semantic_fingerprint: str


@dataclass(frozen=True, slots=True)
class UniverseDelta:
    scope_ref: str
    strategy_version: str
    change_ref: str
    upserts: tuple[UniverseProjectionRoot, ...]
    removals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectionChangeSignal:
    change_ref: str
    fact_kind: str
    fact_id: str
    event_type: str


def to_primitive(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, list):
        return [to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): to_primitive(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        }
    return value


def stable_fingerprint(value) -> str:
    raw = json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
