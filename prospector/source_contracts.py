from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .errors import ProspectorContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ProspectorContractError(f"{name} must not be empty")
    return value


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ProspectorContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _tuple_text(
    name: str,
    values,
    *,
    lower: bool = False,
    strip_prefix: str = "",
) -> Tuple[str, ...]:
    normalized = []
    for value in tuple(values or ()):
        text = _required_text(name, value)
        if strip_prefix and text.startswith(strip_prefix):
            text = text[len(strip_prefix) :]
        if lower:
            text = text.lower()
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _frozen_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProspectorContractError(f"{name} must be a mapping")
    data = dict(value)
    try:
        json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ProspectorContractError(f"{name} must be JSON-serializable") from exc
    return MappingProxyType(data)


@dataclass(frozen=True, slots=True)
class ProspectingMission:
    """Bounded discovery intent; never a manual list of websites to scrape."""

    mission_key: str
    issued_at: datetime
    host_tlds: Tuple[str, ...] = ()
    languages: Tuple[str, ...] = ()
    path_terms: Tuple[str, ...] = ()
    media_types: Tuple[str, ...] = ("text/html",)
    max_candidates: int = 500
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_key", _required_text("mission_key", self.mission_key))
        object.__setattr__(self, "issued_at", _utc_datetime("issued_at", self.issued_at))
        object.__setattr__(
            self,
            "host_tlds",
            _tuple_text("host_tlds", self.host_tlds, lower=True, strip_prefix="."),
        )
        object.__setattr__(
            self,
            "languages",
            _tuple_text("languages", self.languages, lower=True),
        )
        object.__setattr__(
            self,
            "path_terms",
            _tuple_text("path_terms", self.path_terms, lower=True),
        )
        object.__setattr__(
            self,
            "media_types",
            _tuple_text("media_types", self.media_types, lower=True),
        )
        try:
            max_candidates = int(self.max_candidates)
        except (TypeError, ValueError) as exc:
            raise ProspectorContractError("max_candidates must be an integer") from exc
        if not 1 <= max_candidates <= 10000:
            raise ProspectorContractError("max_candidates must be between 1 and 10000")
        object.__setattr__(self, "max_candidates", max_candidates)
        object.__setattr__(self, "context", _frozen_mapping("context", self.context))
        if not self.host_tlds and not self.path_terms:
            raise ProspectorContractError(
                "mission must contain at least one bounded coverage selector: host_tlds or path_terms"
            )

    @property
    def fingerprint(self) -> str:
        payload = {
            "host_tlds": self.host_tlds,
            "languages": self.languages,
            "path_terms": self.path_terms,
            "media_types": self.media_types,
            "max_candidates": self.max_candidates,
            "context": dict(self.context),
        }
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class IndexedResource:
    """A resource reported by an external index, not a Makolo business fact."""

    provider: str
    locator: str
    observed_at: datetime
    source_revision: str
    source_ref: str
    status_code: Optional[int] = None
    mime_type: Optional[str] = None
    language: Optional[str] = None
    registered_domain: Optional[str] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required_text("provider", self.provider))
        object.__setattr__(self, "locator", _required_text("locator", self.locator))
        object.__setattr__(self, "observed_at", _utc_datetime("observed_at", self.observed_at))
        object.__setattr__(
            self,
            "source_revision",
            _required_text("source_revision", self.source_revision),
        )
        object.__setattr__(self, "source_ref", _required_text("source_ref", self.source_ref))
        if self.status_code is not None:
            try:
                status_code = int(self.status_code)
            except (TypeError, ValueError) as exc:
                raise ProspectorContractError("status_code must be an integer") from exc
            if not 100 <= status_code <= 599:
                raise ProspectorContractError("status_code must be a valid HTTP status")
            object.__setattr__(self, "status_code", status_code)
        for field_name in ("mime_type", "language", "registered_domain"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required_text(field_name, value))
        object.__setattr__(
            self,
            "attributes",
            _frozen_mapping("attributes", self.attributes),
        )


@dataclass(frozen=True, slots=True)
class SourceCheckpoint:
    source_name: str
    mission_key: str
    mission_fingerprint: str
    source_revision: str
    cursor: Mapping[str, Any]
    exhausted: bool
    updated_at: datetime

    def __post_init__(self) -> None:
        for name in ("source_name", "mission_key", "mission_fingerprint", "source_revision"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        object.__setattr__(self, "cursor", _frozen_mapping("cursor", self.cursor))
        object.__setattr__(self, "exhausted", bool(self.exhausted))
        object.__setattr__(self, "updated_at", _utc_datetime("updated_at", self.updated_at))


@dataclass(frozen=True, slots=True)
class SourceBatch:
    source_name: str
    source_revision: str
    records: Tuple[IndexedResource, ...]
    next_cursor: Mapping[str, Any] = field(default_factory=dict)
    exhausted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_name", _required_text("source_name", self.source_name))
        object.__setattr__(
            self,
            "source_revision",
            _required_text("source_revision", self.source_revision),
        )
        records = tuple(self.records)
        if not all(isinstance(record, IndexedResource) for record in records):
            raise ProspectorContractError("records must contain IndexedResource values")
        object.__setattr__(self, "records", records)
        object.__setattr__(
            self,
            "next_cursor",
            _frozen_mapping("next_cursor", self.next_cursor),
        )
        object.__setattr__(self, "exhausted", bool(self.exhausted))


@dataclass(frozen=True, slots=True)
class SourceRunResult:
    source_name: str
    source_revision: str
    received: int
    admitted: int
    exhausted: bool
    next_cursor: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_name", _required_text("source_name", self.source_name))
        object.__setattr__(
            self,
            "source_revision",
            _required_text("source_revision", self.source_revision),
        )
        object.__setattr__(self, "next_cursor", _frozen_mapping("next_cursor", self.next_cursor))
