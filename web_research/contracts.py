from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Tuple
from urllib.parse import urlsplit

from research_missions.contracts import ResearchMission


WEB_RESEARCH_CONTRACT_VERSION = 1


class WebResearchContractError(ValueError):
    """Raised when a provider-neutral Web Research contract is invalid."""


class WebResearchMode(str, Enum):
    DISCOVER = "discover"
    DEEPEN = "deepen"
    WATCH = "watch"


class WebResearchOutcome(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    NO_RESULTS = "no_results"
    FAILED = "failed"


class WebResearchStopReason(str, Enum):
    COMPLETED = "completed"
    COVERAGE_SATURATED = "coverage_saturated"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_NEW_CANDIDATES = "no_new_candidates"
    PROVIDER_LIMIT = "provider_limit"
    DEADLINE_REACHED = "deadline_reached"
    FAILED = "failed"


_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "credential",
        "credentials",
        "password",
    }
)


def _text(name: str, value: str | None, *, optional: bool = False, limit: int = 4000) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise WebResearchContractError(f"{name} must be a string")
    value = " ".join(value.split())
    if not value:
        if optional:
            return None
        raise WebResearchContractError(f"{name} must not be empty")
    if len(value) > limit:
        raise WebResearchContractError(f"{name} is too long")
    return value


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise WebResearchContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _code(name: str, value: str) -> str:
    value = _text(name, value, limit=120)
    assert value is not None
    normalized = value.casefold().replace(" ", "_")
    if not normalized[0].isalpha() or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
        for char in normalized
    ):
        raise WebResearchContractError(
            f"{name} must be a stable lowercase technical code"
        )
    return normalized


def _text_tuple(name: str, values, *, required: bool = False, limit: int = 255) -> Tuple[str, ...]:
    result = []
    for value in tuple(values or ()):
        text = _text(name, value, limit=limit)
        assert text is not None
        if text not in result:
            result.append(text)
    if required and not result:
        raise WebResearchContractError(f"{name} must contain at least one value")
    return tuple(result)


def _freeze_json(value):
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def thaw_json(value):
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _contains_sensitive_metadata(value) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in _SENSITIVE_METADATA_KEYS:
                return True
            if _contains_sensitive_metadata(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_sensitive_metadata(item) for item in value)
    return False


def _frozen_mapping(
    name: str,
    value: Mapping[str, Any],
    *,
    reject_sensitive_keys: bool = False,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WebResearchContractError(f"{name} must be a mapping")
    data = dict(value)
    if any(not isinstance(key, str) for key in data):
        raise WebResearchContractError(f"{name} keys must be strings")
    if reject_sensitive_keys and _contains_sensitive_metadata(data):
        raise WebResearchContractError(f"{name} must not contain provider secrets")
    try:
        encoded = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise WebResearchContractError(f"{name} must be JSON-serializable") from exc
    return _freeze_json(json.loads(encoded))


def _digest(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}:v{WEB_RESEARCH_CONTRACT_VERSION}:" + hashlib.sha256(encoded).hexdigest()


def _normalized_locator(locator: str) -> str:
    locator = _text("locator", locator, limit=2000)
    assert locator is not None
    try:
        parsed = urlsplit(locator)
    except ValueError as exc:
        raise WebResearchContractError("locator must be a valid absolute HTTP(S) URL") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise WebResearchContractError("locator must be a valid absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise WebResearchContractError("locator must not contain embedded credentials")
    return locator


def make_web_research_source_ref(locator: str) -> str:
    locator = _normalized_locator(locator)
    return _digest("web-research:source", {"locator": locator})


def make_web_research_candidate_ref(
    *,
    request_ref: str,
    label: str,
    source_refs: Tuple[str, ...],
) -> str:
    request_ref = _text("request_ref", request_ref, limit=255)
    label = _text("label", label, limit=2000)
    refs = _text_tuple("source_refs", source_refs, required=True)
    assert request_ref is not None and label is not None
    return _digest(
        "web-research:candidate",
        {
            "request_ref": request_ref,
            "label": " ".join(label.casefold().split()),
            "source_refs": sorted(refs),
        },
    )


@dataclass(frozen=True, slots=True)
class WebResearchRequest:
    """One bounded execution request backed by an existing ResearchMission."""

    mission: ResearchMission
    mode: WebResearchMode
    requested_at: datetime
    contract_version: int = WEB_RESEARCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.mission, ResearchMission):
            raise WebResearchContractError("mission must be a ResearchMission")
        object.__setattr__(self, "mode", WebResearchMode(self.mode))
        object.__setattr__(self, "requested_at", _aware("requested_at", self.requested_at))
        if self.contract_version != WEB_RESEARCH_CONTRACT_VERSION:
            raise WebResearchContractError("unsupported Web Research contract version")

    @property
    def request_ref(self) -> str:
        return _digest(
            "web-research:request",
            {
                "mission_ref": self.mission.mission_ref,
                "mode": self.mode.value,
                "requested_at": self.requested_at.isoformat(),
            },
        )

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "contract_version": self.contract_version,
            "request_ref": self.request_ref,
            "mode": self.mode.value,
            "requested_at": self.requested_at.isoformat(),
            "mission": dict(self.mission.to_provenance_payload()),
        }


@dataclass(frozen=True, slots=True)
class WebResearchSource:
    """A cited Web source reported by a Web Research engine.

    This is not an Actor-2 artifact and does not pretend that Makolo fetched the
    resource itself.
    """

    source_ref: str
    locator: str
    observed_at: datetime
    title: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        locator = _normalized_locator(self.locator)
        object.__setattr__(self, "locator", locator)
        object.__setattr__(self, "source_ref", _text("source_ref", self.source_ref, limit=255))
        object.__setattr__(self, "observed_at", _aware("observed_at", self.observed_at))
        object.__setattr__(self, "title", _text("title", self.title, optional=True, limit=1000))
        object.__setattr__(
            self,
            "attributes",
            _frozen_mapping("source.attributes", self.attributes),
        )

    @classmethod
    def from_locator(
        cls,
        *,
        locator: str,
        observed_at: datetime,
        title: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> "WebResearchSource":
        return cls(
            source_ref=make_web_research_source_ref(locator),
            locator=locator,
            observed_at=observed_at,
            title=title,
            attributes=attributes or {},
        )

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "source_ref": self.source_ref,
            "locator": self.locator,
            "observed_at": self.observed_at.isoformat(),
            "title": self.title,
            "attributes": thaw_json(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class WebResearchCandidate:
    """A source-backed reality candidate discovered by Web Research.

    It is intentionally lighter than Actor-3 semantic candidates. Attributes may
    carry provider-neutral discovery metadata, but never grants canonical
    business meaning or admission.
    """

    candidate_ref: str
    label: str
    source_refs: Tuple[str, ...]
    type_hints: Tuple[str, ...] = ()
    summary: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "label", _text("label", self.label, limit=2000))
        object.__setattr__(
            self,
            "source_refs",
            _text_tuple("source_refs", self.source_refs, required=True),
        )
        object.__setattr__(
            self,
            "type_hints",
            tuple(dict.fromkeys(_code("type_hint", value) for value in tuple(self.type_hints or ()))),
        )
        object.__setattr__(self, "summary", _text("summary", self.summary, optional=True, limit=4000))
        object.__setattr__(
            self,
            "attributes",
            _frozen_mapping("candidate.attributes", self.attributes),
        )

    @classmethod
    def build(
        cls,
        *,
        request_ref: str,
        label: str,
        source_refs: Tuple[str, ...],
        type_hints: Tuple[str, ...] = (),
        summary: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> "WebResearchCandidate":
        refs = tuple(source_refs)
        return cls(
            candidate_ref=make_web_research_candidate_ref(
                request_ref=request_ref,
                label=label,
                source_refs=refs,
            ),
            label=label,
            source_refs=refs,
            type_hints=type_hints,
            summary=summary,
            attributes=attributes or {},
        )

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "candidate_ref": self.candidate_ref,
            "label": self.label,
            "source_refs": list(self.source_refs),
            "type_hints": list(self.type_hints),
            "summary": self.summary,
            "attributes": thaw_json(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class WebResearchResult:
    """Provider-neutral output of one bounded Web Research execution."""

    request_ref: str
    mission_ref: str
    mode: WebResearchMode
    started_at: datetime
    completed_at: datetime
    outcome: WebResearchOutcome
    stop_reason: WebResearchStopReason
    sources: Tuple[WebResearchSource, ...] = ()
    candidates: Tuple[WebResearchCandidate, ...] = ()
    warning_codes: Tuple[str, ...] = ()
    failure_code: str | None = None
    engine_metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = WEB_RESEARCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_ref", _text("request_ref", self.request_ref, limit=255))
        object.__setattr__(self, "mission_ref", _text("mission_ref", self.mission_ref, limit=255))
        object.__setattr__(self, "mode", WebResearchMode(self.mode))
        object.__setattr__(self, "started_at", _aware("started_at", self.started_at))
        object.__setattr__(self, "completed_at", _aware("completed_at", self.completed_at))
        if self.completed_at < self.started_at:
            raise WebResearchContractError("completed_at precedes started_at")

        outcome = WebResearchOutcome(self.outcome)
        stop_reason = WebResearchStopReason(self.stop_reason)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "stop_reason", stop_reason)

        sources = tuple(self.sources)
        if any(not isinstance(item, WebResearchSource) for item in sources):
            raise WebResearchContractError("sources must contain WebResearchSource values")
        source_refs = [item.source_ref for item in sources]
        if len(source_refs) != len(set(source_refs)):
            raise WebResearchContractError("source refs must be unique")
        object.__setattr__(self, "sources", sources)

        candidates = tuple(self.candidates)
        if any(not isinstance(item, WebResearchCandidate) for item in candidates):
            raise WebResearchContractError("candidates must contain WebResearchCandidate values")
        candidate_refs = [item.candidate_ref for item in candidates]
        if len(candidate_refs) != len(set(candidate_refs)):
            raise WebResearchContractError("candidate refs must be unique")
        known_source_refs = set(source_refs)
        for candidate in candidates:
            if any(ref not in known_source_refs for ref in candidate.source_refs):
                raise WebResearchContractError(
                    "candidate references a source absent from this result"
                )
        object.__setattr__(self, "candidates", candidates)

        object.__setattr__(
            self,
            "warning_codes",
            tuple(dict.fromkeys(_code("warning_code", value) for value in tuple(self.warning_codes or ()))),
        )
        object.__setattr__(
            self,
            "failure_code",
            _text("failure_code", self.failure_code, optional=True, limit=120),
        )
        object.__setattr__(
            self,
            "engine_metadata",
            _frozen_mapping(
                "engine_metadata",
                self.engine_metadata,
                reject_sensitive_keys=True,
            ),
        )

        if self.contract_version != WEB_RESEARCH_CONTRACT_VERSION:
            raise WebResearchContractError("unsupported Web Research contract version")
        if outcome is WebResearchOutcome.FAILED:
            if self.failure_code is None:
                raise WebResearchContractError("failed outcome requires failure_code")
            if candidates:
                raise WebResearchContractError("failed outcome cannot carry candidates")
            if stop_reason is not WebResearchStopReason.FAILED:
                raise WebResearchContractError("failed outcome requires failed stop reason")
        elif self.failure_code is not None:
            raise WebResearchContractError("non-failed outcome cannot carry failure_code")
        if outcome is WebResearchOutcome.NO_RESULTS and candidates:
            raise WebResearchContractError("no_results cannot carry candidates")
        if outcome is WebResearchOutcome.COMPLETED and stop_reason not in {
            WebResearchStopReason.COMPLETED,
            WebResearchStopReason.COVERAGE_SATURATED,
            WebResearchStopReason.NO_NEW_CANDIDATES,
        }:
            raise WebResearchContractError(
                "completed outcome requires a completion stop reason"
            )

    @classmethod
    def from_request(
        cls,
        request: WebResearchRequest,
        *,
        started_at: datetime,
        completed_at: datetime,
        outcome: WebResearchOutcome,
        stop_reason: WebResearchStopReason,
        sources: Tuple[WebResearchSource, ...] = (),
        candidates: Tuple[WebResearchCandidate, ...] = (),
        warning_codes: Tuple[str, ...] = (),
        failure_code: str | None = None,
        engine_metadata: Mapping[str, Any] | None = None,
    ) -> "WebResearchResult":
        if not isinstance(request, WebResearchRequest):
            raise WebResearchContractError("request must be a WebResearchRequest")
        return cls(
            request_ref=request.request_ref,
            mission_ref=request.mission.mission_ref,
            mode=request.mode,
            started_at=started_at,
            completed_at=completed_at,
            outcome=outcome,
            stop_reason=stop_reason,
            sources=sources,
            candidates=candidates,
            warning_codes=warning_codes,
            failure_code=failure_code,
            engine_metadata=engine_metadata or {},
        )

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "contract_version": self.contract_version,
            "request_ref": self.request_ref,
            "mission_ref": self.mission_ref,
            "mode": self.mode.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "outcome": self.outcome.value,
            "stop_reason": self.stop_reason.value,
            "sources": [item.to_payload() for item in self.sources],
            "candidates": [item.to_payload() for item in self.candidates],
            "warning_codes": list(self.warning_codes),
            "failure_code": self.failure_code,
            "engine_metadata": thaw_json(self.engine_metadata),
        }
