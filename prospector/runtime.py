from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from .errors import ProspectorContractError
from .observation_contracts import ObservationDisposition
from .policy import GateDisposition, ObservationPolicy
from .safe_handoff import SafeObservationHandoff


def _positive_int(name: str, value: int, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProspectorContractError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ProspectorContractError(f"{name} must be a {qualifier} integer")
    return value


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
class RuntimePolicy:
    worker_id: str
    claim_batch_size: int
    lease_seconds: int
    exception_retry_seconds: int
    poll_seconds: int
    stop_on_observer_deferred: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", _required_text("worker_id", self.worker_id))
        for name in (
            "claim_batch_size",
            "lease_seconds",
            "exception_retry_seconds",
            "poll_seconds",
        ):
            object.__setattr__(self, name, _positive_int(name, getattr(self, name)))
        if not isinstance(self.stop_on_observer_deferred, bool):
            raise ProspectorContractError(
                "stop_on_observer_deferred must be a boolean"
            )


@dataclass(frozen=True, slots=True)
class RuntimeCycleStats:
    claimed: int = 0
    completed: int = 0
    deferred: int = 0
    suppressed: int = 0
    handoff_errors: int = 0
    backpressure_released: int = 0

    @property
    def transitioned(self) -> int:
        return self.completed + self.deferred + self.suppressed


class ProspectorRuntime:
    """Frontier -> gate -> Observateur coordinator.

    The runtime never owns observation state. A durable ACCEPTED receipt means
    the Observateur owns the handoff. Before that acknowledgement, Frontier
    leases remain the crash-recovery mechanism.
    """

    def __init__(
        self,
        *,
        frontier,
        handoff: SafeObservationHandoff,
        observation_policy: ObservationPolicy,
        runtime_policy: RuntimePolicy,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.frontier = frontier
        self.handoff = handoff
        self.observation_policy = observation_policy
        self.runtime_policy = runtime_policy
        self.clock = clock

    def _now(self) -> datetime:
        value = self.clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ProspectorContractError(
                "runtime clock must return a timezone-aware datetime"
            )
        return value.astimezone(timezone.utc)

    async def run_cycle(self) -> RuntimeCycleStats:
        claims = tuple(
            await self.frontier.claim(
                worker_id=self.runtime_policy.worker_id,
                limit=self.runtime_policy.claim_batch_size,
                lease_seconds=self.runtime_policy.lease_seconds,
            )
        )
        completed = 0
        deferred = 0
        suppressed = 0
        handoff_errors = 0
        backpressure_released = 0
        observer_backpressure_until: Optional[datetime] = None

        for claim in claims:
            if observer_backpressure_until is not None:
                await self.frontier.defer(
                    claim,
                    available_at=observer_backpressure_until,
                )
                deferred += 1
                backpressure_released += 1
                continue

            requested_at = self._now()
            try:
                result = await self.handoff.submit(
                    claim,
                    policy=self.observation_policy,
                    requested_at=requested_at,
                )
            except ProspectorContractError:
                # Contract violations indicate invalid code/data, not transient
                # network pressure. Hiding them behind retry would create loops.
                raise
            except Exception:
                await self.frontier.defer(
                    claim,
                    available_at=requested_at
                    + timedelta(seconds=self.runtime_policy.exception_retry_seconds),
                )
                deferred += 1
                handoff_errors += 1
                continue

            decision = result.decision
            if decision.disposition is GateDisposition.REJECT:
                await self.frontier.suppress(
                    claim,
                    reason_code=decision.reason_code,
                )
                suppressed += 1
                continue
            if decision.disposition is GateDisposition.DEFER:
                await self.frontier.defer(
                    claim,
                    available_at=decision.retry_at,
                )
                deferred += 1
                continue

            receipt = result.receipt
            if receipt.disposition in {
                ObservationDisposition.ACCEPTED,
                ObservationDisposition.ALREADY_ACCEPTED,
            }:
                await self.frontier.complete(claim)
                completed += 1
                continue
            if receipt.disposition is ObservationDisposition.REJECTED:
                await self.frontier.suppress(
                    claim,
                    reason_code=receipt.reason_code,
                )
                suppressed += 1
                continue
            if receipt.disposition is ObservationDisposition.DEFERRED:
                await self.frontier.defer(
                    claim,
                    available_at=receipt.retry_at,
                )
                deferred += 1
                if self.runtime_policy.stop_on_observer_deferred:
                    observer_backpressure_until = receipt.retry_at
                continue

            raise ProspectorContractError(
                f"unsupported observation disposition {receipt.disposition!r}"
            )

        return RuntimeCycleStats(
            claimed=len(claims),
            completed=completed,
            deferred=deferred,
            suppressed=suppressed,
            handoff_errors=handoff_errors,
            backpressure_released=backpressure_released,
        )

    async def run_forever(
        self,
        *,
        stop_event: asyncio.Event,
        on_cycle: Optional[
            Callable[[RuntimeCycleStats], Awaitable[None] | None]
        ] = None,
        on_cycle_error: Optional[
            Callable[[Exception], Awaitable[None] | None]
        ] = None,
        max_cycles: Optional[int] = None,
    ) -> None:
        if max_cycles is not None:
            _positive_int("max_cycles", max_cycles)

        cycles = 0
        while not stop_event.is_set():
            started = time.monotonic()
            try:
                stats = await self.run_cycle()
            except Exception as exc:
                if on_cycle_error is None:
                    raise
                outcome = on_cycle_error(exc)
                if asyncio.iscoroutine(outcome):
                    await outcome
            else:
                if on_cycle is not None:
                    outcome = on_cycle(stats)
                    if asyncio.iscoroutine(outcome):
                        await outcome

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return

            remaining = max(
                self.runtime_policy.poll_seconds - (time.monotonic() - started),
                0.0,
            )
            if remaining <= 0:
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass
