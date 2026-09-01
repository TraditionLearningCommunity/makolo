from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReadinessStatus(str, Enum):
    READY = "ready"
    ACTION_REQUIRED = "action_required"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETE = "complete"


class ReadinessCheckState(str, Enum):
    SATISFIED = "satisfied"
    NOT_APPLICABLE = "not_applicable"
    ACTION_REQUIRED = "action_required"
    WAITING = "waiting"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class NextAction:
    key: str
    label: str
    url: str | None = None
    source: str = "readiness"


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    source: str
    state: ReadinessCheckState
    blocking: bool
    reason_code: str
    summary: str
    next_action: NextAction | None = None


@dataclass(frozen=True)
class ReadinessResult:
    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...]
    next_action: NextAction | None
    observed_at: datetime

    @property
    def is_ready(self):
        return self.status in {ReadinessStatus.READY, ReadinessStatus.COMPLETE}

    @property
    def blocking_items(self):
        return tuple(check for check in self.checks if check.state == ReadinessCheckState.BLOCKING)

    @property
    def waiting_items(self):
        return tuple(check for check in self.checks if check.state == ReadinessCheckState.WAITING)

    @property
    def action_items(self):
        return tuple(check for check in self.checks if check.state == ReadinessCheckState.ACTION_REQUIRED)
