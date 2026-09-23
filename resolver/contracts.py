from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Mapping

from .errors import ResolverContractError
from .identifiers import make_assertion_ref, make_resolution_ref

RESOLVED_MATERIAL_CONTRACT_VERSION = 1
RESOLVER_IMPLEMENTATION_VERSION = "1.0"
_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,119}$")


def _text(name, value, *, optional=False, limit=4000):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ResolverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        if optional:
            return None
        raise ResolverContractError(f"{name} must not be empty")
    if len(value) > limit:
        raise ResolverContractError(f"{name} is too long")
    return value


def _code(name, value):
    value = _text(name, value, limit=120).lower()
    if not _CODE.fullmatch(value):
        raise ResolverContractError(f"{name} must be a stable lowercase technical code")
    return value


def _aware(name, value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResolverContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class ResolutionLifecycle(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FINALIZED = "finalized"


class ResolutionOutcome(str, Enum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"
    UNRESOLVED = "unresolved"
    FAILED = "failed"


class AssertionKind(str, Enum):
    ENTITY = "entity"
    FACT = "fact"
    RELATION = "relation"
    CONSTRAINT = "constraint"
    CONFLICT = "conflict"


class ResolutionStatus(str, Enum):
    MATCHED = "matched"
    NEW_CANDIDATE = "new_candidate"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"
    LINKED = "linked"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    UPDATE = "update"


class ResolutionMethod(str, Enum):
    EXACT = "exact"
    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"


class ResolutionStrength(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    POSSIBLE = "possible"


class EndpointKind(str, Enum):
    CANONICAL = "canonical"
    PROVISIONAL = "provisional"
    CANDIDATE = "candidate"


@dataclass(frozen=True, slots=True)
class CanonicalRef:
    domain: str
    object_ref: str

    def __post_init__(self):
        object.__setattr__(self, "domain", _code("canonical domain", self.domain))
        object.__setattr__(self, "object_ref", _text("canonical object_ref", self.object_ref, limit=255))

    def to_payload(self):
        return {"domain": self.domain, "object_ref": self.object_ref}

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, Mapping):
            raise ResolverContractError("canonical ref payload must be a mapping")
        return cls(payload.get("domain"), payload.get("object_ref"))


@dataclass(frozen=True, slots=True)
class ResolutionAlternative:
    canonical_ref: CanonicalRef
    method: ResolutionMethod
    strength: ResolutionStrength
    basis_codes: tuple[str, ...] = ()
    snapshot_fingerprint: str | None = None

    def __post_init__(self):
        if not isinstance(self.canonical_ref, CanonicalRef):
            raise ResolverContractError("alternative canonical_ref must be CanonicalRef")
        object.__setattr__(self, "method", ResolutionMethod(self.method))
        object.__setattr__(self, "strength", ResolutionStrength(self.strength))
        object.__setattr__(
            self,
            "basis_codes",
            tuple(dict.fromkeys(_code("basis_code", item) for item in self.basis_codes)),
        )
        object.__setattr__(
            self,
            "snapshot_fingerprint",
            _text("snapshot_fingerprint", self.snapshot_fingerprint, optional=True, limit=128),
        )

    def to_payload(self):
        return {
            "canonical_ref": self.canonical_ref.to_payload(),
            "method": self.method.value,
            "strength": self.strength.value,
            "basis_codes": list(self.basis_codes),
            "snapshot_fingerprint": self.snapshot_fingerprint,
        }

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, Mapping):
            raise ResolverContractError("alternative payload must be a mapping")
        return cls(
            canonical_ref=CanonicalRef.from_payload(payload.get("canonical_ref") or {}),
            method=payload.get("method"),
            strength=payload.get("strength"),
            basis_codes=tuple(payload.get("basis_codes") or ()),
            snapshot_fingerprint=payload.get("snapshot_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class ResolutionEndpoint:
    kind: EndpointKind
    ref: str
    canonical_ref: CanonicalRef | None = None

    def __post_init__(self):
        kind = EndpointKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ref", _text("endpoint ref", self.ref, limit=255))
        if kind is EndpointKind.CANONICAL and not isinstance(self.canonical_ref, CanonicalRef):
            raise ResolverContractError("canonical endpoint requires canonical_ref")
        if kind is not EndpointKind.CANONICAL and self.canonical_ref is not None:
            raise ResolverContractError("non-canonical endpoint cannot carry canonical_ref")

    def to_payload(self):
        return {
            "kind": self.kind.value,
            "ref": self.ref,
            "canonical_ref": self.canonical_ref.to_payload() if self.canonical_ref else None,
        }

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, Mapping):
            raise ResolverContractError("endpoint payload must be a mapping")
        canonical = payload.get("canonical_ref")
        return cls(
            kind=payload.get("kind"),
            ref=payload.get("ref"),
            canonical_ref=CanonicalRef.from_payload(canonical) if canonical else None,
        )


@dataclass(frozen=True, slots=True)
class ResolutionAssertion:
    assertion_ref: str
    candidate_ref: str
    kind: AssertionKind
    status: ResolutionStatus
    canonical_ref: CanonicalRef | None = None
    provisional_ref: str | None = None
    subject: ResolutionEndpoint | None = None
    object: ResolutionEndpoint | None = None
    predicate: str | None = None
    method: ResolutionMethod | None = None
    strength: ResolutionStrength | None = None
    basis_codes: tuple[str, ...] = ()
    alternatives: tuple[ResolutionAlternative, ...] = ()
    related_candidate_refs: tuple[str, ...] = ()
    candidate_payload: Mapping = field(default_factory=dict)
    semantic_fingerprint: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "kind", AssertionKind(self.kind))
        object.__setattr__(self, "status", ResolutionStatus(self.status))
        if self.canonical_ref is not None and not isinstance(self.canonical_ref, CanonicalRef):
            raise ResolverContractError("canonical_ref must be CanonicalRef")
        object.__setattr__(self, "provisional_ref", _text("provisional_ref", self.provisional_ref, optional=True, limit=255))
        if self.subject is not None and not isinstance(self.subject, ResolutionEndpoint):
            raise ResolverContractError("subject must be ResolutionEndpoint")
        if self.object is not None and not isinstance(self.object, ResolutionEndpoint):
            raise ResolverContractError("object must be ResolutionEndpoint")
        object.__setattr__(self, "predicate", _code("predicate", self.predicate) if self.predicate is not None else None)
        object.__setattr__(self, "method", ResolutionMethod(self.method) if self.method is not None else None)
        object.__setattr__(self, "strength", ResolutionStrength(self.strength) if self.strength is not None else None)
        object.__setattr__(
            self,
            "basis_codes",
            tuple(dict.fromkeys(_code("basis_code", item) for item in self.basis_codes)),
        )
        object.__setattr__(self, "alternatives", tuple(self.alternatives))
        if any(not isinstance(item, ResolutionAlternative) for item in self.alternatives):
            raise ResolverContractError("alternatives must contain ResolutionAlternative")
        object.__setattr__(
            self,
            "related_candidate_refs",
            tuple(dict.fromkeys(_text("related_candidate_ref", item, limit=255) for item in self.related_candidate_refs)),
        )
        if not isinstance(self.candidate_payload, Mapping):
            raise ResolverContractError("candidate_payload must be a mapping")
        object.__setattr__(self, "candidate_payload", dict(self.candidate_payload))
        object.__setattr__(
            self,
            "semantic_fingerprint",
            _text("semantic_fingerprint", self.semantic_fingerprint, optional=True, limit=128),
        )
        if self.status is ResolutionStatus.MATCHED and self.canonical_ref is None:
            raise ResolverContractError("matched assertion requires canonical_ref")
        if self.status is ResolutionStatus.NEW_CANDIDATE and self.provisional_ref is None:
            raise ResolverContractError("new_candidate assertion requires provisional_ref")
        if self.canonical_ref is not None and self.provisional_ref is not None:
            raise ResolverContractError("assertion cannot be canonical and provisional simultaneously")

    def semantic_payload(self):
        return {
            "candidate_ref": self.candidate_ref,
            "kind": self.kind.value,
            "status": self.status.value,
            "canonical_ref": self.canonical_ref.to_payload() if self.canonical_ref else None,
            "provisional_ref": self.provisional_ref,
            "subject": self.subject.to_payload() if self.subject else None,
            "object": self.object.to_payload() if self.object else None,
            "predicate": self.predicate,
            "method": self.method.value if self.method else None,
            "strength": self.strength.value if self.strength else None,
            "basis_codes": list(self.basis_codes),
            "alternatives": [item.to_payload() for item in self.alternatives],
            "related_candidate_refs": list(self.related_candidate_refs),
            "candidate_payload": dict(self.candidate_payload),
            "semantic_fingerprint": self.semantic_fingerprint,
        }

    def to_payload(self):
        return {"assertion_ref": self.assertion_ref, **self.semantic_payload()}

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, Mapping):
            raise ResolverContractError("assertion payload must be a mapping")
        canonical = payload.get("canonical_ref")
        subject = payload.get("subject")
        obj = payload.get("object")
        return cls(
            assertion_ref=payload.get("assertion_ref"),
            candidate_ref=payload.get("candidate_ref"),
            kind=payload.get("kind"),
            status=payload.get("status"),
            canonical_ref=CanonicalRef.from_payload(canonical) if canonical else None,
            provisional_ref=payload.get("provisional_ref"),
            subject=ResolutionEndpoint.from_payload(subject) if subject else None,
            object=ResolutionEndpoint.from_payload(obj) if obj else None,
            predicate=payload.get("predicate"),
            method=payload.get("method"),
            strength=payload.get("strength"),
            basis_codes=tuple(payload.get("basis_codes") or ()),
            alternatives=tuple(ResolutionAlternative.from_payload(item) for item in payload.get("alternatives") or ()),
            related_candidate_refs=tuple(payload.get("related_candidate_refs") or ()),
            candidate_payload=dict(payload.get("candidate_payload") or {}),
            semantic_fingerprint=payload.get("semantic_fingerprint"),
        )


def assign_assertion_ref(*, resolution_ref: str, assertion: ResolutionAssertion) -> ResolutionAssertion:
    from dataclasses import replace

    semantic = assertion.semantic_payload()
    ref = make_assertion_ref(
        resolution_ref=resolution_ref,
        kind=assertion.kind.value,
        candidate_ref=assertion.candidate_ref,
        payload=semantic,
    )
    return replace(assertion, assertion_ref=ref)


@dataclass(frozen=True, slots=True)
class ResolvedMaterial:
    resolution_ref: str
    interpretation_ref: str
    material_key: str
    observation_ref: str
    target_key: str
    strategy_key: str
    strategy_version: str
    strategy_fingerprint: str
    started_at: datetime
    completed_at: datetime
    outcome: ResolutionOutcome
    assertions: tuple[ResolutionAssertion, ...] = ()
    warning_codes: tuple[str, ...] = ()
    failure_code: str | None = None
    contract_version: int = RESOLVED_MATERIAL_CONTRACT_VERSION

    def __post_init__(self):
        for name, limit in (
            ("interpretation_ref", 255),
            ("material_key", 255),
            ("observation_ref", 255),
            ("target_key", 96),
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name), limit=limit))
        object.__setattr__(self, "strategy_key", _code("strategy_key", self.strategy_key))
        object.__setattr__(self, "strategy_version", _text("strategy_version", self.strategy_version, limit=80))
        object.__setattr__(self, "strategy_fingerprint", _text("strategy_fingerprint", self.strategy_fingerprint, limit=128))
        expected = make_resolution_ref(
            interpretation_ref=self.interpretation_ref,
            strategy_fingerprint=self.strategy_fingerprint,
        )
        if self.resolution_ref != expected:
            raise ResolverContractError("resolution_ref is inconsistent")
        object.__setattr__(self, "started_at", _aware("started_at", self.started_at))
        object.__setattr__(self, "completed_at", _aware("completed_at", self.completed_at))
        if self.completed_at < self.started_at:
            raise ResolverContractError("completed_at precedes started_at")
        object.__setattr__(self, "outcome", ResolutionOutcome(self.outcome))
        assertions = tuple(self.assertions)
        refs = {item.assertion_ref for item in assertions}
        if len(refs) != len(assertions):
            raise ResolverContractError("assertion refs must be unique")
        object.__setattr__(self, "assertions", assertions)
        object.__setattr__(
            self,
            "warning_codes",
            tuple(dict.fromkeys(_code("warning_code", item) for item in self.warning_codes)),
        )
        object.__setattr__(self, "failure_code", _text("failure_code", self.failure_code, optional=True, limit=120))
        if self.contract_version != 1:
            raise ResolverContractError("unsupported resolved material contract version")
        if self.outcome is ResolutionOutcome.FAILED and self.failure_code is None:
            raise ResolverContractError("failed outcome requires failure_code")
        if self.outcome is not ResolutionOutcome.FAILED and self.failure_code is not None:
            raise ResolverContractError("non-failed outcome cannot carry failure_code")

    @property
    def entity_resolutions(self):
        return tuple(item for item in self.assertions if item.kind is AssertionKind.ENTITY)

    @property
    def fact_resolutions(self):
        return tuple(item for item in self.assertions if item.kind is AssertionKind.FACT)

    @property
    def relation_resolutions(self):
        return tuple(item for item in self.assertions if item.kind is AssertionKind.RELATION)

    @property
    def constraint_resolutions(self):
        return tuple(item for item in self.assertions if item.kind is AssertionKind.CONSTRAINT)

    @property
    def conflicts(self):
        return tuple(item for item in self.assertions if item.kind is AssertionKind.CONFLICT)
