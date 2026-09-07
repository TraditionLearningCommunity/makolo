from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class ImpactChannel(str, Enum):
    CAPACITY = "capacity"
    COVERAGE = "coverage"
    ACTIONABILITY = "actionability"
    REAL_ACTION = "real_action"
    ECONOMIC = "economic"
    RELIABILITY = "reliability"
    DURABILITY = "durability"
    PROMOTIONAL = "promotional"


class TemporalProfile(str, Enum):
    PULSE = "pulse"
    WINDOW = "window"
    STOCK = "stock"
    FLOW = "flow"
    TRANSITION = "transition"


class RecognitionWindowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RecognitionLedgerKind(str, Enum):
    GRANT = "grant"
    SPEND = "spend"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True, slots=True)
class RecognitionSliceCandidate:
    """Domain-independent candidate emitted by a Recognition adapter."""

    slice_key: str
    accrual_key: str
    channel: ImpactChannel
    temporal_profile: TemporalProfile
    occurred_at: datetime
    available_at: datetime
    impact_delta: Decimal
    attribution_shares: tuple[Any, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RecognitionSignalFact:
    """Pure signal contract consumed by the policy engine, with no ORM dependency."""

    signal_id: str
    signal_kind: str
    object_type: str
    object_id: str
    occurred_at: datetime
    available_at: datetime
    outcome_identity: str
    values: dict[str, Any] = field(default_factory=dict)
    contributors: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    confidence: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class PolicyRuleResult:
    rule_code: str
    channel: ImpactChannel
    temporal_profile: TemporalProfile
    utility_delta: Decimal
    accrual_key: str
    slice_key: str
    attribution_shares: tuple[Any, ...] = field(default_factory=tuple)
    explanation: dict[str, Any] = field(default_factory=dict)
