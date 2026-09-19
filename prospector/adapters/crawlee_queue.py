from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from crawlee import Request

from prospector.errors import ProspectorContractError
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
    ObservationTarget,
)


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ProspectorContractError(f"{name} must not be empty")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CrawleeQueuePolicy:
    queue_name: str
    max_pending_requests: int
    capacity_retry_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "queue_name", _required_text("queue_name", self.queue_name))
        if (
            not isinstance(self.max_pending_requests, int)
            or isinstance(self.max_pending_requests, bool)
            or self.max_pending_requests < 0
        ):
            raise ProspectorContractError(
                "max_pending_requests must be a non-negative integer"
            )
        if (
            not isinstance(self.capacity_retry_seconds, int)
            or isinstance(self.capacity_retry_seconds, bool)
            or self.capacity_retry_seconds < 1
        ):
            raise ProspectorContractError(
                "capacity_retry_seconds must be a positive integer"
            )


class CrawleeObservationInbox:
    """Crawlee RequestQueue adapter for Prospecteur -> Observateur.

    The queue is an execution inbox, never the Makolo Frontier or business
    truth. The caller must inject an Observer-owned RequestQueue configured
    with persistence appropriate to its deployment.
    """

    REQUEST_LABEL = "makolo-observation"

    def __init__(
        self,
        *,
        request_queue,
        policy: CrawleeQueuePolicy,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.request_queue = request_queue
        self.policy = policy
        self.clock = clock

    def _now(self) -> datetime:
        value = self.clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ProspectorContractError(
                "Crawlee inbox clock must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    def _observer_ref(self, handoff_key: str) -> str:
        return f"crawlee:{self.policy.queue_name}:{handoff_key}"

    async def submit(self, target: ObservationTarget) -> ObservationReceipt:
        if not isinstance(target, ObservationTarget):
            raise ProspectorContractError("target must be an ObservationTarget")

        now = self._now()

        # Duplicate lookup happens before capacity: an already-owned handoff must
        # remain idempotently acknowledged even while the queue is saturated.
        existing = await self.request_queue.get_request(target.handoff_key)
        if existing is not None:
            return ObservationReceipt(
                handoff_key=target.handoff_key,
                target_key=target.target_key,
                handoff_generation=target.handoff_generation,
                disposition=ObservationDisposition.ALREADY_ACCEPTED,
                received_at=now,
                observer_ref=self._observer_ref(target.handoff_key),
            )

        total = await self.request_queue.get_total_count()
        handled = await self.request_queue.get_handled_count()
        pending = max(int(total) - int(handled), 0)
        if pending >= self.policy.max_pending_requests:
            return ObservationReceipt(
                handoff_key=target.handoff_key,
                target_key=target.target_key,
                handoff_generation=target.handoff_generation,
                disposition=ObservationDisposition.DEFERRED,
                received_at=now,
                reason_code="observer.capacity",
                retry_at=now
                + timedelta(seconds=self.policy.capacity_retry_seconds),
            )

        request = Request.from_url(
            target.locator,
            unique_key=target.handoff_key,
            label=self.REQUEST_LABEL,
            user_data={
                "makolo": {
                    "contract_version": target.contract_version,
                    "target_key": target.target_key,
                    "handoff_key": target.handoff_key,
                    "handoff_generation": target.handoff_generation,
                    "requested_at": target.requested_at.isoformat(),
                    "observation_hints": dict(target.observation_hints),
                }
            },
        )
        added = await self.request_queue.add_request(request)
        disposition = (
            ObservationDisposition.ACCEPTED
            if added is not None
            else ObservationDisposition.ALREADY_ACCEPTED
        )
        return ObservationReceipt(
            handoff_key=target.handoff_key,
            target_key=target.target_key,
            handoff_generation=target.handoff_generation,
            disposition=disposition,
            received_at=now,
            observer_ref=self._observer_ref(target.handoff_key),
        )
