from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.common.fingerprints import semantic_fingerprint


SENSITIVE_METADATA_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "private_key",
    "access_token",
    "refresh_token",
    "credential",
)


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MayeleContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MayeleContractError(f"{name} must be timezone-aware")
    return value


def _scope_rank(scope: KnowledgeScope) -> int:
    return {
        ScopeVisibility.PUBLIC: 0,
        ScopeVisibility.RESTRICTED: 1,
        ScopeVisibility.PRIVATE: 2,
    }[scope.visibility]


def _derived_scope(
    parent: KnowledgeScope, child: Optional[KnowledgeScope]
) -> KnowledgeScope:
    if child is None:
        return parent
    if not isinstance(child, KnowledgeScope):
        raise MayeleContractError("scope must be KnowledgeScope")
    if _scope_rank(child) < _scope_rank(parent):
        raise MayeleContractError("knowledge scope cannot be widened implicitly")
    if parent.context_ref is not None and child.context_ref != parent.context_ref:
        raise MayeleContractError(
            "derived non-public knowledge must preserve its parent context_ref"
        )
    return child


def _freeze_metadata(
    metadata: Mapping[str, Any] | Tuple[Tuple[str, Any], ...],
    *,
    scope: KnowledgeScope,
) -> Tuple[Tuple[str, Any], ...]:
    if isinstance(metadata, Mapping):
        items = tuple(sorted(metadata.items(), key=lambda pair: str(pair[0])))
    else:
        items = tuple(metadata)

    frozen: list[tuple[str, Any]] = []
    for key, value in items:
        if not isinstance(key, str) or not key.strip():
            raise MayeleContractError("metadata keys must be non-empty strings")
        normalized_key = key.strip()
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise MayeleContractError("metadata values must be scalar JSON values")
        if scope.visibility is ScopeVisibility.PUBLIC:
            folded = normalized_key.casefold()
            if any(token in folded for token in SENSITIVE_METADATA_TOKENS):
                raise MayeleContractError(
                    "public observation metadata must not contain secrets or credentials"
                )
        frozen.append((normalized_key, value))
    return tuple(frozen)


def sha256_digest(content: bytes | str) -> str:
    """Return a deterministic content digest without retaining the content."""

    if isinstance(content, str):
        raw = content.encode("utf-8")
    elif isinstance(content, bytes):
        raw = content
    else:
        raise MayeleContractError("digest content must be bytes or str")
    return hashlib.sha256(raw).hexdigest()


def _content_digest(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MayeleContractError("content_digest must be a hexadecimal SHA-256 string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise MayeleContractError("content_digest must be a hexadecimal SHA-256 string")
    return normalized


class SourceKind(str, Enum):
    WEB_PAGE = "WEB_PAGE"
    API_ENDPOINT = "API_ENDPOINT"
    DOCUMENT = "DOCUMENT"
    CONNECTED_FILE = "CONNECTED_FILE"
    EMAIL = "EMAIL"
    FEED = "FEED"
    PARTNER_SYSTEM = "PARTNER_SYSTEM"
    REPOSITORY = "REPOSITORY"
    PUBLICATION = "PUBLICATION"
    OTHER = "OTHER"


class ObservationChannel(str, Enum):
    WEB = "WEB"
    API = "API"
    FILE = "FILE"
    EMAIL = "EMAIL"
    FEED = "FEED"
    CONNECTOR = "CONNECTOR"
    PARTNER = "PARTNER"
    REPOSITORY = "REPOSITORY"
    OTHER = "OTHER"


class ObservationAttemptOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    DENIED = "DENIED"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Source:
    """Logical origin Mayele can attempt to observe; never the received content."""

    source_ref: str
    kind: SourceKind
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    locator: Optional[str] = None
    label: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ref", _required_text("source_ref", self.source_ref))
        try:
            kind = SourceKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid source kind") from exc
        object.__setattr__(self, "kind", kind)
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        object.__setattr__(self, "locator", _optional_text("locator", self.locator))
        object.__setattr__(self, "label", _optional_text("label", self.label))

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "source_ref": self.source_ref,
                "kind": self.kind.value,
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class ObservationAttempt:
    attempt_ref: str
    source: Source
    attempted_at: datetime
    outcome: ObservationAttemptOutcome
    scope: Optional[KnowledgeScope] = None
    channel: Optional[ObservationChannel] = None
    retry_of_attempt_ref: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "attempt_ref", _required_text("attempt_ref", self.attempt_ref)
        )
        if not isinstance(self.source, Source):
            raise MayeleContractError("source must be Source")
        object.__setattr__(
            self, "attempted_at", _aware_datetime("attempted_at", self.attempted_at)
        )
        try:
            outcome = ObservationAttemptOutcome(self.outcome)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid observation attempt outcome") from exc
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "scope", _derived_scope(self.source.scope, self.scope))
        if self.channel is not None:
            try:
                channel = ObservationChannel(self.channel)
            except (TypeError, ValueError) as exc:
                raise MayeleContractError("invalid observation channel") from exc
            object.__setattr__(self, "channel", channel)
        object.__setattr__(
            self,
            "retry_of_attempt_ref",
            _optional_text("retry_of_attempt_ref", self.retry_of_attempt_ref),
        )
        if self.retry_of_attempt_ref == self.attempt_ref:
            raise MayeleContractError("an attempt cannot retry itself")

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "attempt_ref": self.attempt_ref,
                "source_ref": self.source.source_ref,
                "attempted_at": self.attempted_at,
                "outcome": self.outcome.value,
                "scope": self.scope.to_payload(),
                "channel": self.channel.value if self.channel else None,
                "retry_of_attempt_ref": self.retry_of_attempt_ref,
            }
        )


@dataclass(frozen=True, slots=True)
class Observation:
    """A successful temporal observation event, distinct from its content."""

    observation_ref: str
    attempt: ObservationAttempt
    observed_at: datetime
    scope: Optional[KnowledgeScope] = None
    source_version_ref: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        if not isinstance(self.attempt, ObservationAttempt):
            raise MayeleContractError("attempt must be ObservationAttempt")
        if self.attempt.outcome is not ObservationAttemptOutcome.SUCCESS:
            raise MayeleContractError(
                "only a successful observation attempt can produce an Observation"
            )
        object.__setattr__(
            self, "observed_at", _aware_datetime("observed_at", self.observed_at)
        )
        object.__setattr__(self, "scope", _derived_scope(self.attempt.scope, self.scope))
        object.__setattr__(
            self,
            "source_version_ref",
            _optional_text("source_version_ref", self.source_version_ref),
        )

    @property
    def source(self) -> Source:
        return self.attempt.source

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "observation_ref": self.observation_ref,
                "attempt_ref": self.attempt.attempt_ref,
                "source_ref": self.source.source_ref,
                "observed_at": self.observed_at,
                "scope": self.scope.to_payload(),
                "source_version_ref": self.source_version_ref,
            }
        )


@dataclass(frozen=True, slots=True)
class ObservedArtifact:
    artifact_ref: str
    observation: Observation
    content_type: str
    content_digest: Optional[str] = None
    scope: Optional[KnowledgeScope] = None
    metadata: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_ref", _required_text("artifact_ref", self.artifact_ref)
        )
        if not isinstance(self.observation, Observation):
            raise MayeleContractError("observation must be Observation")
        object.__setattr__(
            self, "content_type", _required_text("content_type", self.content_type)
        )
        object.__setattr__(
            self, "content_digest", _content_digest(self.content_digest)
        )
        scope = _derived_scope(self.observation.scope, self.scope)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, scope=scope)
        )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "artifact_ref": self.artifact_ref,
                "observation_ref": self.observation.observation_ref,
                "content_type": self.content_type,
                "content_digest": self.content_digest,
                "scope": self.scope.to_payload(),
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True, slots=True)
class Passage:
    passage_ref: str
    artifact: ObservedArtifact
    address: str
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "passage_ref", _required_text("passage_ref", self.passage_ref)
        )
        if not isinstance(self.artifact, ObservedArtifact):
            raise MayeleContractError("artifact must be ObservedArtifact")
        object.__setattr__(self, "address", _required_text("address", self.address))
        object.__setattr__(self, "scope", _derived_scope(self.artifact.scope, self.scope))

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "passage_ref": self.passage_ref,
                "artifact_ref": self.artifact.artifact_ref,
                "address": self.address,
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class ObservedStatement:
    statement_ref: str
    passage: Passage
    text: str
    scope: Optional[KnowledgeScope] = None
    language: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "statement_ref", _required_text("statement_ref", self.statement_ref)
        )
        if not isinstance(self.passage, Passage):
            raise MayeleContractError("passage must be Passage")
        object.__setattr__(self, "text", _required_text("text", self.text))
        object.__setattr__(self, "scope", _derived_scope(self.passage.scope, self.scope))
        object.__setattr__(self, "language", _optional_text("language", self.language))

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "statement_ref": self.statement_ref,
                "passage_ref": self.passage.passage_ref,
                "text": self.text,
                "scope": self.scope.to_payload(),
                "language": self.language,
            }
        )


@dataclass(frozen=True, slots=True)
class Mention:
    mention_ref: str
    statement: ObservedStatement
    surface: str
    scope: Optional[KnowledgeScope] = None
    start: Optional[int] = None
    end: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mention_ref", _required_text("mention_ref", self.mention_ref)
        )
        if not isinstance(self.statement, ObservedStatement):
            raise MayeleContractError("statement must be ObservedStatement")
        object.__setattr__(self, "surface", _required_text("surface", self.surface))
        object.__setattr__(
            self, "scope", _derived_scope(self.statement.scope, self.scope)
        )
        if (self.start is None) != (self.end is None):
            raise MayeleContractError("mention start and end must be provided together")
        if self.start is not None:
            if not isinstance(self.start, int) or not isinstance(self.end, int):
                raise MayeleContractError("mention offsets must be integers")
            if self.start < 0 or self.end <= self.start or self.end > len(self.statement.text):
                raise MayeleContractError("mention offsets must address the statement text")
            if self.statement.text[self.start : self.end] != self.surface:
                raise MayeleContractError("mention surface must match the addressed statement span")

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "mention_ref": self.mention_ref,
                "statement_ref": self.statement.statement_ref,
                "surface": self.surface,
                "scope": self.scope.to_payload(),
                "start": self.start,
                "end": self.end,
            }
        )
