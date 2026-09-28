from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Sequence, runtime_checkable

from .contracts import (
    WebResearchCandidate,
    WebResearchContractError,
    WebResearchResult,
    WebResearchSource,
)


DISCOVERY_OUTPUT_CONTRACT_VERSION = 1


class DiscoveryKnowledgeState(str, Enum):
    """What Makolo can safely conclude about one discovered candidate."""

    KNOWN = "known"
    NOT_KNOWN = "not_known"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class DiscoveryKnownRef:
    domain: str
    object_ref: str

    def __post_init__(self) -> None:
        domain = (self.domain or "").strip().lower()
        object_ref = (self.object_ref or "").strip()
        if not domain or not domain[0].isalpha() or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
            for char in domain
        ):
            raise WebResearchContractError(
                "discovery known-ref domain must be a stable technical code"
            )
        if not object_ref:
            raise WebResearchContractError(
                "discovery known-ref object_ref must not be empty"
            )
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "object_ref", object_ref)

    def to_payload(self):
        return {"domain": self.domain, "object_ref": self.object_ref}


@dataclass(frozen=True, slots=True)
class DiscoveryLookup:
    state: DiscoveryKnowledgeState
    known_refs: tuple[DiscoveryKnownRef, ...] = ()
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        state = DiscoveryKnowledgeState(self.state)
        object.__setattr__(self, "state", state)
        known_refs = tuple(self.known_refs)
        if any(not isinstance(item, DiscoveryKnownRef) for item in known_refs):
            raise WebResearchContractError(
                "known_refs must contain DiscoveryKnownRef values"
            )
        if len({(item.domain, item.object_ref) for item in known_refs}) != len(
            known_refs
        ):
            raise WebResearchContractError("known_refs must be unique")
        object.__setattr__(self, "known_refs", known_refs)
        basis_codes = []
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
                    "basis_codes must contain stable technical codes"
                )
            if value not in basis_codes:
                basis_codes.append(value)
        object.__setattr__(self, "basis_codes", tuple(basis_codes))

        if state is DiscoveryKnowledgeState.KNOWN and len(known_refs) != 1:
            raise WebResearchContractError(
                "known discovery lookup requires exactly one known_ref"
            )
        if state is DiscoveryKnowledgeState.AMBIGUOUS and len(known_refs) < 2:
            raise WebResearchContractError(
                "ambiguous discovery lookup requires at least two known_refs"
            )
        if state in {
            DiscoveryKnowledgeState.NOT_KNOWN,
            DiscoveryKnowledgeState.UNRESOLVED,
        } and known_refs:
            raise WebResearchContractError(
                "not_known/unresolved discovery lookup cannot carry known_refs"
            )


@runtime_checkable
class DiscoveryKnowledgePort(Protocol):
    """Read-only bounded knowledge check used before deeper resolution.

    NOT_KNOWN is a strong statement: implementations may emit it only when the
    bounded catalog they own is sufficient to establish absence for that lookup.
    When coverage is incomplete they must return UNRESOLVED instead.
    """

    def lookup(
        self,
        *,
        result: WebResearchResult,
        candidate: WebResearchCandidate,
        sources: tuple[WebResearchSource, ...],
    ) -> DiscoveryLookup:
        ...


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    candidate_ref: str
    label: str
    source_refs: tuple[str, ...]
    type_hints: tuple[str, ...]
    summary: str | None
    knowledge_state: DiscoveryKnowledgeState
    known_refs: tuple[DiscoveryKnownRef, ...] = ()
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_ref:
            raise WebResearchContractError("candidate_ref must not be empty")
        if not self.label:
            raise WebResearchContractError("label must not be empty")
        object.__setattr__(self, "source_refs", tuple(self.source_refs))
        object.__setattr__(self, "type_hints", tuple(self.type_hints))
        object.__setattr__(
            self, "knowledge_state", DiscoveryKnowledgeState(self.knowledge_state)
        )
        lookup = DiscoveryLookup(
            state=self.knowledge_state,
            known_refs=tuple(self.known_refs),
            basis_codes=tuple(self.basis_codes),
        )
        object.__setattr__(self, "known_refs", lookup.known_refs)
        object.__setattr__(self, "basis_codes", lookup.basis_codes)

    def to_payload(self):
        return {
            "candidate_ref": self.candidate_ref,
            "label": self.label,
            "source_refs": list(self.source_refs),
            "type_hints": list(self.type_hints),
            "summary": self.summary,
            "knowledge_state": self.knowledge_state.value,
            "known_refs": [item.to_payload() for item in self.known_refs],
            "basis_codes": list(self.basis_codes),
        }


@dataclass(frozen=True, slots=True)
class DiscoveryOutput:
    """Stable provider-neutral output consumed by downstream Makolo stages."""

    request_ref: str
    mission_ref: str
    research_outcome: str
    stop_reason: str
    generated_at: datetime
    source_count: int
    records: tuple[DiscoveryRecord, ...] = ()
    warning_codes: tuple[str, ...] = ()
    contract_version: int = DISCOVERY_OUTPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.request_ref or not self.mission_ref:
            raise WebResearchContractError(
                "discovery output requires request_ref and mission_ref"
            )
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise WebResearchContractError(
                "discovery output generated_at must be timezone-aware"
            )
        object.__setattr__(
            self, "generated_at", self.generated_at.astimezone(timezone.utc)
        )
        if (
            not isinstance(self.source_count, int)
            or isinstance(self.source_count, bool)
            or self.source_count < 0
        ):
            raise WebResearchContractError(
                "discovery output source_count must be non-negative"
            )
        records = tuple(self.records)
        if any(not isinstance(item, DiscoveryRecord) for item in records):
            raise WebResearchContractError(
                "discovery output records must contain DiscoveryRecord"
            )
        refs = [item.candidate_ref for item in records]
        if len(refs) != len(set(refs)):
            raise WebResearchContractError(
                "discovery output candidate refs must be unique"
            )
        object.__setattr__(self, "records", records)
        object.__setattr__(
            self,
            "warning_codes",
            tuple(dict.fromkeys(str(item) for item in self.warning_codes)),
        )
        if self.contract_version != DISCOVERY_OUTPUT_CONTRACT_VERSION:
            raise WebResearchContractError(
                "unsupported discovery output contract version"
            )

    @property
    def candidate_count(self) -> int:
        return len(self.records)

    @property
    def counts_by_state(self) -> dict[str, int]:
        counts = {state.value: 0 for state in DiscoveryKnowledgeState}
        for record in self.records:
            counts[record.knowledge_state.value] += 1
        return counts

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "request_ref": self.request_ref,
            "mission_ref": self.mission_ref,
            "research_outcome": self.research_outcome,
            "stop_reason": self.stop_reason,
            "generated_at": self.generated_at.isoformat(),
            "source_count": self.source_count,
            "candidate_count": self.candidate_count,
            "counts_by_state": self.counts_by_state,
            "records": [item.to_payload() for item in self.records],
            "warning_codes": list(self.warning_codes),
        }


class DiscoveryNormalizer:
    """Convert one WebResearchResult into the standard DiscoveryOutput v1."""

    def __init__(self, knowledge: DiscoveryKnowledgePort):
        self.knowledge = knowledge

    def normalize(self, result: WebResearchResult) -> DiscoveryOutput:
        if not isinstance(result, WebResearchResult):
            raise WebResearchContractError(
                "result must be a WebResearchResult"
            )

        source_by_ref = {item.source_ref: item for item in result.sources}
        records = []
        warnings = list(result.warning_codes)

        for candidate in result.candidates:
            sources = tuple(source_by_ref[ref] for ref in candidate.source_refs)
            lookup = self.knowledge.lookup(
                result=result,
                candidate=candidate,
                sources=sources,
            )
            if not isinstance(lookup, DiscoveryLookup):
                raise WebResearchContractError(
                    "knowledge lookup must return DiscoveryLookup"
                )
            records.append(
                DiscoveryRecord(
                    candidate_ref=candidate.candidate_ref,
                    label=candidate.label,
                    source_refs=candidate.source_refs,
                    type_hints=candidate.type_hints,
                    summary=candidate.summary,
                    knowledge_state=lookup.state,
                    known_refs=lookup.known_refs,
                    basis_codes=lookup.basis_codes,
                )
            )

        return DiscoveryOutput(
            request_ref=result.request_ref,
            mission_ref=result.mission_ref,
            research_outcome=result.outcome.value,
            stop_reason=result.stop_reason.value,
            generated_at=result.completed_at,
            source_count=len(result.sources),
            records=tuple(records),
            warning_codes=tuple(warnings),
        )
