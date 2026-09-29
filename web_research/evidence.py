from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping

from research_missions import ResearchFamily

from .contracts import WebResearchContractError, WebResearchResult


EVIDENCE_OUTPUT_CONTRACT_VERSION = 1
EVIDENCE_FINDINGS_ATTRIBUTE = "evidence_findings_v1"


class EvidenceState(str, Enum):
    """Epistemic state of one Web Research finding."""

    OBSERVED = "observed"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


def _text(name: str, value, *, optional: bool = False, limit: int = 4000):
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


def _code(name: str, value) -> str:
    value = _text(name, value, limit=120)
    normalized = value.casefold().replace(" ", "_")
    if not normalized[0].isalpha() or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
        for char in normalized
    ):
        raise WebResearchContractError(
            f"{name} must be a stable lowercase technical code"
        )
    return normalized


def _aware(name: str, value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise WebResearchContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _source_refs(values, *, required: bool = False) -> tuple[str, ...]:
    refs = []
    for value in tuple(values or ()):
        value = _text("source_ref", value, limit=255)
        if value not in refs:
            refs.append(value)
    if required and not refs:
        raise WebResearchContractError("finding requires at least one source_ref")
    return tuple(refs)


def _basis_codes(values) -> tuple[str, ...]:
    result = []
    for value in tuple(values or ()):
        code = _code("basis_code", value)
        if code not in result:
            result.append(code)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class EvidenceAlternative:
    """One supported alternative inside a conflicting finding."""

    state: EvidenceState
    source_refs: tuple[str, ...]
    value_text: str | None = None

    def __post_init__(self) -> None:
        state = EvidenceState(self.state)
        if state not in {
            EvidenceState.OBSERVED,
            EvidenceState.NOT_APPLICABLE,
        }:
            raise WebResearchContractError(
                "evidence alternative must be observed or not_applicable"
            )
        object.__setattr__(self, "state", state)
        refs = _source_refs(self.source_refs, required=True)
        object.__setattr__(self, "source_refs", refs)
        value = _text(
            "value_text",
            self.value_text,
            optional=True,
            limit=4000,
        )
        if state is EvidenceState.OBSERVED and value is None:
            raise WebResearchContractError(
                "observed evidence alternative requires value_text"
            )
        if state is EvidenceState.NOT_APPLICABLE and value is not None:
            raise WebResearchContractError(
                "not_applicable evidence alternative cannot carry value_text"
            )
        object.__setattr__(self, "value_text", value)

    def to_payload(self):
        return {
            "state": self.state.value,
            "value_text": self.value_text,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class EvidenceFinding:
    """One fact-level Web Research finding with explicit epistemic state."""

    candidate_ref: str
    family: ResearchFamily
    predicate: str
    state: EvidenceState
    observed_at: datetime
    value_text: str | None = None
    source_refs: tuple[str, ...] = ()
    alternatives: tuple[EvidenceAlternative, ...] = ()
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_ref",
            _text("candidate_ref", self.candidate_ref, limit=255),
        )
        object.__setattr__(self, "family", ResearchFamily(self.family))
        object.__setattr__(self, "predicate", _code("predicate", self.predicate))
        state = EvidenceState(self.state)
        object.__setattr__(self, "state", state)
        object.__setattr__(
            self,
            "observed_at",
            _aware("observed_at", self.observed_at),
        )
        value = _text(
            "value_text",
            self.value_text,
            optional=True,
            limit=4000,
        )
        refs = _source_refs(self.source_refs)
        alternatives = tuple(self.alternatives)
        if any(not isinstance(item, EvidenceAlternative) for item in alternatives):
            raise WebResearchContractError(
                "alternatives must contain EvidenceAlternative values"
            )
        object.__setattr__(self, "basis_codes", _basis_codes(self.basis_codes))

        if state is EvidenceState.OBSERVED:
            if value is None or not refs or alternatives:
                raise WebResearchContractError(
                    "observed finding requires value and sources, without alternatives"
                )
        elif state is EvidenceState.UNKNOWN:
            if value is not None or alternatives:
                raise WebResearchContractError(
                    "unknown finding cannot carry a value or alternatives"
                )
            if not refs and not self.basis_codes:
                raise WebResearchContractError(
                    "unknown finding requires source context or a basis code"
                )
        elif state is EvidenceState.NOT_APPLICABLE:
            if value is not None or not refs or alternatives:
                raise WebResearchContractError(
                    "not_applicable finding requires sourced support and no value"
                )
        elif state is EvidenceState.CONFLICTING:
            if value is not None or refs or len(alternatives) < 2:
                raise WebResearchContractError(
                    "conflicting finding requires at least two alternatives"
                )
            signatures = {
                (item.state.value, item.value_text)
                for item in alternatives
            }
            if len(signatures) < 2:
                raise WebResearchContractError(
                    "conflicting alternatives must describe distinct states or values"
                )

        object.__setattr__(self, "value_text", value)
        object.__setattr__(self, "source_refs", refs)
        object.__setattr__(self, "alternatives", alternatives)

    @property
    def support_source_refs(self) -> tuple[str, ...]:
        refs = list(self.source_refs)
        for alternative in self.alternatives:
            for source_ref in alternative.source_refs:
                if source_ref not in refs:
                    refs.append(source_ref)
        return tuple(refs)

    def to_payload(self):
        return {
            "candidate_ref": self.candidate_ref,
            "family": self.family.value,
            "predicate": self.predicate,
            "state": self.state.value,
            "observed_at": self.observed_at.isoformat(),
            "value_text": self.value_text,
            "source_refs": list(self.source_refs),
            "alternatives": [item.to_payload() for item in self.alternatives],
            "basis_codes": list(self.basis_codes),
        }


@dataclass(frozen=True, slots=True)
class EvidenceOutput:
    """Provider-neutral fact-level evidence projected from Web Research."""

    request_ref: str
    mission_ref: str
    generated_at: datetime
    findings: tuple[EvidenceFinding, ...] = ()
    warning_codes: tuple[str, ...] = ()
    contract_version: int = EVIDENCE_OUTPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_ref",
            _text("request_ref", self.request_ref, limit=255),
        )
        object.__setattr__(
            self,
            "mission_ref",
            _text("mission_ref", self.mission_ref, limit=255),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware("generated_at", self.generated_at),
        )
        findings = tuple(self.findings)
        if any(not isinstance(item, EvidenceFinding) for item in findings):
            raise WebResearchContractError(
                "evidence output findings must contain EvidenceFinding"
            )
        keys = [
            (item.candidate_ref, item.family.value, item.predicate)
            for item in findings
        ]
        if len(keys) != len(set(keys)):
            raise WebResearchContractError(
                "evidence output must contain one finding per candidate/family/predicate"
            )
        object.__setattr__(self, "findings", findings)
        object.__setattr__(
            self,
            "warning_codes",
            tuple(dict.fromkeys(str(item) for item in self.warning_codes)),
        )
        if self.contract_version != EVIDENCE_OUTPUT_CONTRACT_VERSION:
            raise WebResearchContractError(
                "unsupported evidence output contract version"
            )

    @property
    def counts_by_state(self) -> dict[str, int]:
        counts = {state.value: 0 for state in EvidenceState}
        for finding in self.findings:
            counts[finding.state.value] += 1
        return counts

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "request_ref": self.request_ref,
            "mission_ref": self.mission_ref,
            "generated_at": self.generated_at.isoformat(),
            "finding_count": len(self.findings),
            "counts_by_state": self.counts_by_state,
            "findings": [item.to_payload() for item in self.findings],
            "warning_codes": list(self.warning_codes),
        }


class EvidenceNormalizer:
    """Normalize validated fact-level transport rows into EvidenceOutput v1.

    Transport rows are allowed only through the reserved provider-neutral
    candidate attribute. They are validated again here. This output remains
    distinct from Actor-3 CandidateEvidence because Web Search citations are not
    Observer artifacts.
    """

    def normalize(self, result: WebResearchResult) -> EvidenceOutput:
        if not isinstance(result, WebResearchResult):
            raise WebResearchContractError(
                "result must be a WebResearchResult"
            )

        source_refs = {item.source_ref for item in result.sources}
        warnings = list(result.warning_codes)
        groups: dict[tuple[str, ResearchFamily, str], list[dict]] = {}

        for candidate in result.candidates:
            raw_rows = candidate.attributes.get(EVIDENCE_FINDINGS_ATTRIBUTE, ())
            if raw_rows in (None, ()):
                continue
            if not isinstance(raw_rows, (list, tuple)):
                warnings.append("evidence_findings_invalid")
                continue

            allowed_refs = set(candidate.source_refs)
            for raw in raw_rows:
                if not isinstance(raw, Mapping):
                    warnings.append("evidence_finding_invalid")
                    continue
                try:
                    family = ResearchFamily(raw.get("family"))
                    predicate = _code("predicate", raw.get("predicate"))
                    state = EvidenceState(raw.get("state"))
                    if state is EvidenceState.CONFLICTING:
                        raise WebResearchContractError(
                            "transport cannot declare conflicting directly"
                        )
                    value = _text(
                        "value_text",
                        raw.get("value_text"),
                        optional=True,
                        limit=4000,
                    )
                    refs = _source_refs(raw.get("source_refs") or ())
                    if any(
                        ref not in source_refs or ref not in allowed_refs
                        for ref in refs
                    ):
                        warnings.append("evidence_finding_unknown_source")
                        continue
                    if state is EvidenceState.OBSERVED and (
                        value is None or not refs
                    ):
                        raise WebResearchContractError(
                            "observed transport finding requires value and sources"
                        )
                    if state is EvidenceState.UNKNOWN and value is not None:
                        raise WebResearchContractError(
                            "unknown transport finding cannot carry value"
                        )
                    if state is EvidenceState.NOT_APPLICABLE and (
                        value is not None or not refs
                    ):
                        raise WebResearchContractError(
                            "not_applicable transport finding requires sources and no value"
                        )
                except (TypeError, ValueError, WebResearchContractError):
                    warnings.append("evidence_finding_invalid")
                    continue

                groups.setdefault(
                    (candidate.candidate_ref, family, predicate),
                    [],
                ).append(
                    {
                        "state": state,
                        "value_text": value,
                        "source_refs": refs,
                    }
                )

        findings = []
        for (candidate_ref, family, predicate), rows in groups.items():
            observed: dict[str, dict] = {}
            not_applicable_refs = []
            unknown_refs = []

            for row in rows:
                state = row["state"]
                refs = row["source_refs"]
                if state is EvidenceState.OBSERVED:
                    semantic_key = " ".join(
                        row["value_text"].casefold().split()
                    )
                    current = observed.setdefault(
                        semantic_key,
                        {
                            "value_text": row["value_text"],
                            "source_refs": [],
                        },
                    )
                    for ref in refs:
                        if ref not in current["source_refs"]:
                            current["source_refs"].append(ref)
                elif state is EvidenceState.NOT_APPLICABLE:
                    for ref in refs:
                        if ref not in not_applicable_refs:
                            not_applicable_refs.append(ref)
                else:
                    for ref in refs:
                        if ref not in unknown_refs:
                            unknown_refs.append(ref)

            alternatives = [
                EvidenceAlternative(
                    state=EvidenceState.OBSERVED,
                    value_text=item["value_text"],
                    source_refs=tuple(item["source_refs"]),
                )
                for item in observed.values()
            ]
            if not_applicable_refs:
                alternatives.append(
                    EvidenceAlternative(
                        state=EvidenceState.NOT_APPLICABLE,
                        source_refs=tuple(not_applicable_refs),
                    )
                )

            if len(alternatives) >= 2:
                findings.append(
                    EvidenceFinding(
                        candidate_ref=candidate_ref,
                        family=family,
                        predicate=predicate,
                        state=EvidenceState.CONFLICTING,
                        observed_at=result.completed_at,
                        alternatives=tuple(alternatives),
                        basis_codes=("multiple_supported_values",),
                    )
                )
            elif alternatives:
                alternative = alternatives[0]
                findings.append(
                    EvidenceFinding(
                        candidate_ref=candidate_ref,
                        family=family,
                        predicate=predicate,
                        state=alternative.state,
                        observed_at=result.completed_at,
                        value_text=alternative.value_text,
                        source_refs=alternative.source_refs,
                        basis_codes=("web_research_structured_finding",),
                    )
                )
            else:
                findings.append(
                    EvidenceFinding(
                        candidate_ref=candidate_ref,
                        family=family,
                        predicate=predicate,
                        state=EvidenceState.UNKNOWN,
                        observed_at=result.completed_at,
                        source_refs=tuple(unknown_refs),
                        basis_codes=("web_research_not_established",),
                    )
                )

        return EvidenceOutput(
            request_ref=result.request_ref,
            mission_ref=result.mission_ref,
            generated_at=result.completed_at,
            findings=tuple(findings),
            warning_codes=tuple(warnings),
        )
