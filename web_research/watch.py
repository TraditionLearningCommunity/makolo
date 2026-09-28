from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

from .contracts import WebResearchContractError, WebResearchSource
from .discovery import DiscoveryKnownRef, DiscoveryOutput


WATCH_OUTPUT_CONTRACT_VERSION = 1


class WatchFreshnessState(str, Enum):
    FRESH = "fresh"
    DUE = "due"
    UNRESOLVED = "unresolved"


class WatchChangeState(str, Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    UNREACHABLE = "unreachable"
    REMOVED = "removed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Simple generic policy for deciding whether a known source needs a check."""

    max_age_seconds: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_age_seconds, int)
            or isinstance(self.max_age_seconds, bool)
            or self.max_age_seconds < 1
        ):
            raise WebResearchContractError(
                "max_age_seconds must be a positive integer"
            )

    @property
    def max_age(self) -> timedelta:
        return timedelta(seconds=self.max_age_seconds)

    def to_payload(self):
        return {"max_age_seconds": self.max_age_seconds}


@dataclass(frozen=True, slots=True)
class WatchLookup:
    freshness_state: WatchFreshnessState
    known_ref: DiscoveryKnownRef | None = None
    last_checked_at: datetime | None = None
    due_at: datetime | None = None
    last_change_state: WatchChangeState = WatchChangeState.UNKNOWN
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        state = WatchFreshnessState(self.freshness_state)
        change = WatchChangeState(self.last_change_state)
        object.__setattr__(self, "freshness_state", state)
        object.__setattr__(self, "last_change_state", change)

        if self.known_ref is not None and not isinstance(
            self.known_ref, DiscoveryKnownRef
        ):
            raise WebResearchContractError(
                "watch known_ref must be DiscoveryKnownRef"
            )

        for name in ("last_checked_at", "due_at"):
            value = getattr(self, name)
            if value is None:
                continue
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise WebResearchContractError(
                    f"{name} must be timezone-aware"
                )
            object.__setattr__(self, name, value.astimezone(timezone.utc))

        if state in {
            WatchFreshnessState.FRESH,
            WatchFreshnessState.DUE,
        } and self.known_ref is None:
            raise WebResearchContractError(
                "fresh/due watch lookup requires known_ref"
            )
        if state is WatchFreshnessState.FRESH:
            if self.last_checked_at is None or self.due_at is None:
                raise WebResearchContractError(
                    "fresh lookup requires last_checked_at and due_at"
                )
        if state is WatchFreshnessState.DUE and self.due_at is None:
            raise WebResearchContractError("due lookup requires due_at")
        if state is WatchFreshnessState.UNRESOLVED and self.known_ref is not None:
            raise WebResearchContractError(
                "unresolved lookup cannot carry known_ref"
            )

        normalized = []
        for value in tuple(self.basis_codes or ()):
            value = str(value).strip().lower()
            if (
                not value
                or not value[0].isalpha()
                or any(
                    char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
                    for char in value
                )
            ):
                raise WebResearchContractError(
                    "watch basis_codes must contain stable technical codes"
                )
            if value not in normalized:
                normalized.append(value)
        object.__setattr__(self, "basis_codes", tuple(normalized))


@runtime_checkable
class WatchKnowledgePort(Protocol):
    def assess(
        self,
        *,
        source: WebResearchSource,
        now: datetime,
        policy: FreshnessPolicy,
    ) -> WatchLookup:
        ...


@dataclass(frozen=True, slots=True)
class WatchTarget:
    source_ref: str
    locator: str
    freshness_state: WatchFreshnessState
    known_ref: DiscoveryKnownRef | None = None
    last_checked_at: datetime | None = None
    due_at: datetime | None = None
    last_change_state: WatchChangeState = WatchChangeState.UNKNOWN
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        lookup = WatchLookup(
            freshness_state=self.freshness_state,
            known_ref=self.known_ref,
            last_checked_at=self.last_checked_at,
            due_at=self.due_at,
            last_change_state=self.last_change_state,
            basis_codes=self.basis_codes,
        )
        object.__setattr__(self, "freshness_state", lookup.freshness_state)
        object.__setattr__(self, "known_ref", lookup.known_ref)
        object.__setattr__(self, "last_checked_at", lookup.last_checked_at)
        object.__setattr__(self, "due_at", lookup.due_at)
        object.__setattr__(self, "last_change_state", lookup.last_change_state)
        object.__setattr__(self, "basis_codes", lookup.basis_codes)

    def to_payload(self):
        return {
            "source_ref": self.source_ref,
            "locator": self.locator,
            "freshness_state": self.freshness_state.value,
            "known_ref": self.known_ref.to_payload() if self.known_ref else None,
            "last_checked_at": (
                self.last_checked_at.isoformat()
                if self.last_checked_at is not None
                else None
            ),
            "due_at": self.due_at.isoformat() if self.due_at is not None else None,
            "last_change_state": self.last_change_state.value,
            "basis_codes": list(self.basis_codes),
        }


@dataclass(frozen=True, slots=True)
class WatchOutput:
    """Standard provider-neutral watch planning output."""

    discovery_request_ref: str
    generated_at: datetime
    policy: FreshnessPolicy
    targets: tuple[WatchTarget, ...] = ()
    contract_version: int = WATCH_OUTPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.discovery_request_ref:
            raise WebResearchContractError(
                "watch output requires discovery_request_ref"
            )
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise WebResearchContractError(
                "watch output generated_at must be timezone-aware"
            )
        object.__setattr__(
            self,
            "generated_at",
            self.generated_at.astimezone(timezone.utc),
        )
        if not isinstance(self.policy, FreshnessPolicy):
            raise WebResearchContractError(
                "watch output policy must be FreshnessPolicy"
            )
        targets = tuple(self.targets)
        if any(not isinstance(item, WatchTarget) for item in targets):
            raise WebResearchContractError(
                "watch output targets must contain WatchTarget"
            )
        refs = [item.source_ref for item in targets]
        if len(refs) != len(set(refs)):
            raise WebResearchContractError(
                "watch output source refs must be unique"
            )
        object.__setattr__(self, "targets", targets)
        if self.contract_version != WATCH_OUTPUT_CONTRACT_VERSION:
            raise WebResearchContractError(
                "unsupported watch output contract version"
            )

    @property
    def counts_by_state(self) -> dict[str, int]:
        counts = {state.value: 0 for state in WatchFreshnessState}
        for target in self.targets:
            counts[target.freshness_state.value] += 1
        return counts

    @property
    def due_source_refs(self) -> tuple[str, ...]:
        return tuple(
            item.source_ref
            for item in self.targets
            if item.freshness_state is WatchFreshnessState.DUE
        )

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "discovery_request_ref": self.discovery_request_ref,
            "generated_at": self.generated_at.isoformat(),
            "policy": self.policy.to_payload(),
            "target_count": len(self.targets),
            "counts_by_state": self.counts_by_state,
            "due_source_refs": list(self.due_source_refs),
            "targets": [item.to_payload() for item in self.targets],
        }


class WatchPlanner:
    """Plan source rechecks without scheduling or mutating owner domains."""

    def __init__(self, knowledge: WatchKnowledgePort):
        self.knowledge = knowledge

    def plan(
        self,
        *,
        discovery: DiscoveryOutput,
        sources: tuple[WebResearchSource, ...],
        policy: FreshnessPolicy,
        generated_at: datetime,
    ) -> WatchOutput:
        if not isinstance(discovery, DiscoveryOutput):
            raise WebResearchContractError(
                "discovery must be a DiscoveryOutput"
            )
        if not isinstance(policy, FreshnessPolicy):
            raise WebResearchContractError(
                "policy must be a FreshnessPolicy"
            )
        if (
            not isinstance(generated_at, datetime)
            or generated_at.tzinfo is None
            or generated_at.utcoffset() is None
        ):
            raise WebResearchContractError(
                "generated_at must be timezone-aware"
            )
        now = generated_at.astimezone(timezone.utc)

        source_by_ref = {item.source_ref: item for item in sources}
        required_refs = {
            source_ref
            for record in discovery.records
            for source_ref in record.source_refs
        }
        missing_refs = required_refs - set(source_by_ref)
        if missing_refs:
            raise WebResearchContractError(
                "watch planner is missing Discovery source material"
            )

        targets = []
        for source_ref in sorted(required_refs):
            source = source_by_ref[source_ref]
            lookup = self.knowledge.assess(
                source=source,
                now=now,
                policy=policy,
            )
            if not isinstance(lookup, WatchLookup):
                raise WebResearchContractError(
                    "watch knowledge must return WatchLookup"
                )
            targets.append(
                WatchTarget(
                    source_ref=source.source_ref,
                    locator=source.locator,
                    freshness_state=lookup.freshness_state,
                    known_ref=lookup.known_ref,
                    last_checked_at=lookup.last_checked_at,
                    due_at=lookup.due_at,
                    last_change_state=lookup.last_change_state,
                    basis_codes=lookup.basis_codes,
                )
            )

        return WatchOutput(
            discovery_request_ref=discovery.request_ref,
            generated_at=now,
            policy=policy,
            targets=tuple(targets),
        )
