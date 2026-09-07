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
    """Domain-independent candidate emitted by a Recognition adapter.

    ``slice_key`` is globally stable and is the anti-double-processing identity.
    ``available_at`` is when Recognition could first consume the observation;
    it may be later than ``occurred_at`` and is what evaluation windows use.
    ``accrual_key`` groups successive slices that must share one cumulative
    impact-to-points curve, for example one Opportunity/channel or one
    Activity/channel.
    """

    slice_key: str
    accrual_key: str
    channel: ImpactChannel
    temporal_profile: TemporalProfile
    occurred_at: datetime
    available_at: datetime
    impact_delta: Decimal
    attribution_shares: tuple[Any, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
