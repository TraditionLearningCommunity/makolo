from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
from typing import Mapping

from .errors import InterpreterContractError
from .identifiers import make_candidate_ref, make_interpretation_ref

INTERPRETED_MATERIAL_CONTRACT_VERSION = 1
INTERPRETER_IMPLEMENTATION_VERSION = "1.0"
_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,119}$")
_LANG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def _text(name, value, *, optional=False, limit=4000):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise InterpreterContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        if optional:
            return None
        raise InterpreterContractError(f"{name} must not be empty")
    if len(value) > limit:
        raise InterpreterContractError(f"{name} is too long")
    return value


def _code(name, value):
    value = _text(name, value, limit=120).lower()
    if not _CODE.fullmatch(value):
        raise InterpreterContractError(f"{name} must be a stable lowercase technical code")
    return value


def _aware(name, value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InterpreterContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(name, value):
    if isinstance(value, bool):
        raise InterpreterContractError(f"{name} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InterpreterContractError(f"{name} must be numeric") from exc
    if not result.is_finite():
        raise InterpreterContractError(f"{name} must be finite")
    return result


class InterpretationLifecycle(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FINALIZED = "finalized"


class InterpretationOutcome(str, Enum):
    INTERPRETED = "interpreted"
    PARTIAL = "partial"
    NO_USEFUL_INFORMATION = "no_useful_information"
    FAILED = "failed"


class CandidateKind(str, Enum):
    ENTITY = "entity"
    FACT = "fact"
    RELATION = "relation"
    CONSTRAINT = "constraint"


class CandidateModality(str, Enum):
    ASSERTED = "asserted"
    REQUIRED = "required"
    OPTIONAL = "optional"
    RECOMMENDED = "recommended"
    PROHIBITED = "prohibited"
    NEGATED = "negated"
    CONDITIONAL = "conditional"


class CandidateValueKind(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    QUANTITY = "quantity"
    MONEY = "money"


class ConstraintOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BETWEEN = "between"
    IN = "in"


class LogicOperator(str, Enum):
    AND = "and"
    OR = "or"


class EvidenceLocatorKind(str, Enum):
    ARTIFACT = "artifact"
    TEXT_SPAN = "text_span"
    JSON_POINTER = "json_pointer"
    HTML_PATH = "html_path"
    XML_PATH = "xml_path"
    PDF_PAGE = "pdf_page"


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    artifact_ref: str
    artifact_observation_ref: str
    locator_kind: EvidenceLocatorKind = EvidenceLocatorKind.ARTIFACT
    locator: str | None = None
    extraction_method: str = "artifact"
    start_offset: int | None = None
    end_offset: int | None = None
    page_number: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "artifact_ref", _text("artifact_ref", self.artifact_ref, limit=255))
        object.__setattr__(self, "artifact_observation_ref", _text("artifact_observation_ref", self.artifact_observation_ref, limit=255))
        object.__setattr__(self, "locator_kind", EvidenceLocatorKind(self.locator_kind))
        object.__setattr__(self, "locator", _text("locator", self.locator, optional=True, limit=1000))
        object.__setattr__(self, "extraction_method", _code("extraction_method", self.extraction_method))
        for name in ("start_offset", "end_offset", "page_number"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise InterpreterContractError(f"{name} must be a non-negative integer")
        if self.end_offset is not None and self.start_offset is not None and self.end_offset < self.start_offset:
            raise InterpreterContractError("end_offset must not precede start_offset")
        if self.page_number is not None and self.page_number < 1:
            raise InterpreterContractError("page_number must be >= 1")

    def to_payload(self):
        return {
            "artifact_ref": self.artifact_ref,
            "artifact_observation_ref": self.artifact_observation_ref,
            "locator_kind": self.locator_kind.value,
            "locator": self.locator,
            "extraction_method": self.extraction_method,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "page_number": self.page_number,
        }


@dataclass(frozen=True, slots=True)
class CandidateValue:
    kind: CandidateValueKind
    raw_text: str | None = None
    text: str | None = None
    number: Decimal | None = None
    boolean: bool | None = None
    date_value: date | None = None
    datetime_value: datetime | None = None
    unit: str | None = None
    currency: str | None = None
    language: str | None = None

    def __post_init__(self):
        kind = CandidateValueKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "raw_text", _text("raw_text", self.raw_text, optional=True, limit=2000))
        object.__setattr__(self, "text", _text("text", self.text, optional=True))
        object.__setattr__(self, "unit", _text("unit", self.unit, optional=True, limit=80))
        currency = _text("currency", self.currency, optional=True, limit=3)
        if currency:
            currency = currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise InterpreterContractError("currency must be a three-letter code")
        object.__setattr__(self, "currency", currency)
        language = _text("language", self.language, optional=True, limit=35)
        if language and not _LANG.fullmatch(language):
            raise InterpreterContractError("language must be a BCP47-like tag")
        object.__setattr__(self, "language", language)
        if self.number is not None:
            object.__setattr__(self, "number", _decimal("number", self.number))
        if self.datetime_value is not None:
            object.__setattr__(self, "datetime_value", _aware("datetime_value", self.datetime_value))
        valid = {
            CandidateValueKind.TEXT: self.text is not None,
            CandidateValueKind.NUMBER: self.number is not None,
            CandidateValueKind.BOOLEAN: isinstance(self.boolean, bool),
            CandidateValueKind.DATE: isinstance(self.date_value, date) and not isinstance(self.date_value, datetime),
            CandidateValueKind.DATETIME: self.datetime_value is not None,
            CandidateValueKind.QUANTITY: self.number is not None and self.unit is not None,
            CandidateValueKind.MONEY: self.number is not None and self.currency is not None,
        }[kind]
        if not valid:
            raise InterpreterContractError(f"incomplete {kind.value} candidate value")
        if kind is not CandidateValueKind.QUANTITY and self.unit is not None:
            raise InterpreterContractError("unit is only valid for quantity")
        if kind is not CandidateValueKind.MONEY and self.currency is not None:
            raise InterpreterContractError("currency is only valid for money")

    def to_payload(self):
        return {
            "kind": self.kind.value,
            "raw_text": self.raw_text,
            "text": self.text,
            "number": str(self.number) if self.number is not None else None,
            "boolean": self.boolean,
            "date": self.date_value.isoformat() if self.date_value is not None else None,
            "datetime": self.datetime_value.isoformat() if self.datetime_value is not None else None,
            "unit": self.unit,
            "currency": self.currency,
            "language": self.language,
        }

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, Mapping):
            raise InterpreterContractError("candidate value payload must be a mapping")
        return cls(
            kind=payload.get("kind"),
            raw_text=payload.get("raw_text"),
            text=payload.get("text"),
            number=payload.get("number"),
            boolean=payload.get("boolean"),
            date_value=date.fromisoformat(payload["date"]) if payload.get("date") else None,
            datetime_value=datetime.fromisoformat(payload["datetime"]) if payload.get("datetime") else None,
            unit=payload.get("unit"),
            currency=payload.get("currency"),
            language=payload.get("language"),
        )


@dataclass(frozen=True, slots=True)
class CandidateEntity:
    candidate_ref: str
    label: str
    type_hints: tuple[str, ...] = ()
    language: str | None = None
    evidence: tuple[CandidateEvidence, ...] = ()
    kind: CandidateKind = field(default=CandidateKind.ENTITY, init=False)

    def __post_init__(self):
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "label", _text("label", self.label, limit=2000))
        object.__setattr__(self, "type_hints", tuple(dict.fromkeys(_code("type_hint", item) for item in self.type_hints)))
        language = _text("language", self.language, optional=True, limit=35)
        if language and not _LANG.fullmatch(language):
            raise InterpreterContractError("language must be a BCP47-like tag")
        object.__setattr__(self, "language", language)
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def semantic_payload(self):
        return {"label": self.label, "type_hints": list(self.type_hints), "language": self.language}


@dataclass(frozen=True, slots=True)
class CandidateFact:
    candidate_ref: str
    predicate: str
    value: CandidateValue
    subject_ref: str | None = None
    modality: CandidateModality = CandidateModality.ASSERTED
    condition_ref: str | None = None
    evidence: tuple[CandidateEvidence, ...] = ()
    kind: CandidateKind = field(default=CandidateKind.FACT, init=False)

    def __post_init__(self):
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "predicate", _code("predicate", self.predicate))
        object.__setattr__(self, "subject_ref", _text("subject_ref", self.subject_ref, optional=True, limit=255))
        object.__setattr__(self, "condition_ref", _text("condition_ref", self.condition_ref, optional=True, limit=255))
        if not isinstance(self.value, CandidateValue):
            raise InterpreterContractError("fact value must be CandidateValue")
        object.__setattr__(self, "modality", CandidateModality(self.modality))
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def semantic_payload(self):
        return {"subject_ref": self.subject_ref, "predicate": self.predicate, "value": self.value.to_payload(), "modality": self.modality.value, "condition_ref": self.condition_ref}


@dataclass(frozen=True, slots=True)
class CandidateRelation:
    candidate_ref: str
    subject_ref: str
    predicate: str
    object_ref: str
    modality: CandidateModality = CandidateModality.ASSERTED
    condition_ref: str | None = None
    logic_group: str | None = None
    logic_operator: LogicOperator | None = None
    evidence: tuple[CandidateEvidence, ...] = ()
    kind: CandidateKind = field(default=CandidateKind.RELATION, init=False)

    def __post_init__(self):
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "subject_ref", _text("subject_ref", self.subject_ref, limit=255))
        object.__setattr__(self, "predicate", _code("predicate", self.predicate))
        object.__setattr__(self, "object_ref", _text("object_ref", self.object_ref, limit=255))
        object.__setattr__(self, "condition_ref", _text("condition_ref", self.condition_ref, optional=True, limit=255))
        object.__setattr__(self, "logic_group", _text("logic_group", self.logic_group, optional=True, limit=120))
        object.__setattr__(self, "modality", CandidateModality(self.modality))
        logic = LogicOperator(self.logic_operator) if self.logic_operator is not None else None
        if logic is not None and self.logic_group is None:
            raise InterpreterContractError("logic_operator requires logic_group")
        object.__setattr__(self, "logic_operator", logic)
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def semantic_payload(self):
        return {"subject_ref": self.subject_ref, "predicate": self.predicate, "object_ref": self.object_ref, "modality": self.modality.value, "condition_ref": self.condition_ref, "logic_group": self.logic_group, "logic_operator": self.logic_operator.value if self.logic_operator else None}


@dataclass(frozen=True, slots=True)
class CandidateConstraint:
    candidate_ref: str
    subject_ref: str
    predicate: str
    operator: ConstraintOperator
    value: CandidateValue
    second_value: CandidateValue | None = None
    logic_group: str | None = None
    logic_operator: LogicOperator | None = None
    evidence: tuple[CandidateEvidence, ...] = ()
    kind: CandidateKind = field(default=CandidateKind.CONSTRAINT, init=False)

    def __post_init__(self):
        object.__setattr__(self, "candidate_ref", _text("candidate_ref", self.candidate_ref, limit=255))
        object.__setattr__(self, "subject_ref", _text("subject_ref", self.subject_ref, limit=255))
        object.__setattr__(self, "predicate", _code("predicate", self.predicate))
        object.__setattr__(self, "operator", ConstraintOperator(self.operator))
        if not isinstance(self.value, CandidateValue):
            raise InterpreterContractError("constraint value must be CandidateValue")
        if self.second_value is not None and not isinstance(self.second_value, CandidateValue):
            raise InterpreterContractError("second_value must be CandidateValue")
        if self.operator is ConstraintOperator.BETWEEN and self.second_value is None:
            raise InterpreterContractError("between requires second_value")
        if self.operator is not ConstraintOperator.BETWEEN and self.second_value is not None:
            raise InterpreterContractError("second_value is only valid for between")
        object.__setattr__(self, "logic_group", _text("logic_group", self.logic_group, optional=True, limit=120))
        logic = LogicOperator(self.logic_operator) if self.logic_operator is not None else None
        if logic is not None and self.logic_group is None:
            raise InterpreterContractError("logic_operator requires logic_group")
        object.__setattr__(self, "logic_operator", logic)
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def semantic_payload(self):
        return {"subject_ref": self.subject_ref, "predicate": self.predicate, "operator": self.operator.value, "value": self.value.to_payload(), "second_value": self.second_value.to_payload() if self.second_value else None, "logic_group": self.logic_group, "logic_operator": self.logic_operator.value if self.logic_operator else None}


Candidate = CandidateEntity | CandidateFact | CandidateRelation | CandidateConstraint


@dataclass(frozen=True, slots=True)
class ArtifactUse:
    artifact_ref: str
    artifact_observation_ref: str
    role: str
    media_type: str | None
    content_digest: str
    selection_reason: str
    completeness: str

    def __post_init__(self):
        object.__setattr__(self, "artifact_ref", _text("artifact_ref", self.artifact_ref, limit=255))
        object.__setattr__(self, "artifact_observation_ref", _text("artifact_observation_ref", self.artifact_observation_ref, limit=255))
        object.__setattr__(self, "role", _text("role", self.role, limit=64))
        object.__setattr__(self, "media_type", _text("media_type", self.media_type, optional=True, limit=180))
        digest = _text("content_digest", self.content_digest, limit=64).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise InterpreterContractError("content_digest must be SHA-256")
        object.__setattr__(self, "content_digest", digest)
        object.__setattr__(self, "selection_reason", _code("selection_reason", self.selection_reason))
        object.__setattr__(self, "completeness", _code("completeness", self.completeness))


@dataclass(frozen=True, slots=True)
class InterpretedMaterial:
    interpretation_ref: str
    material_key: str
    observation_ref: str
    target_key: str
    strategy_key: str
    strategy_version: str
    strategy_fingerprint: str
    started_at: datetime
    completed_at: datetime
    outcome: InterpretationOutcome
    candidates: tuple[Candidate, ...] = ()
    artifact_uses: tuple[ArtifactUse, ...] = ()
    warning_codes: tuple[str, ...] = ()
    failure_code: str | None = None
    contract_version: int = INTERPRETED_MATERIAL_CONTRACT_VERSION

    def __post_init__(self):
        object.__setattr__(self, "material_key", _text("material_key", self.material_key, limit=255))
        object.__setattr__(self, "observation_ref", _text("observation_ref", self.observation_ref, limit=255))
        object.__setattr__(self, "target_key", _text("target_key", self.target_key, limit=96))
        object.__setattr__(self, "strategy_key", _code("strategy_key", self.strategy_key))
        object.__setattr__(self, "strategy_version", _text("strategy_version", self.strategy_version, limit=80))
        object.__setattr__(self, "strategy_fingerprint", _text("strategy_fingerprint", self.strategy_fingerprint, limit=128))
        expected = make_interpretation_ref(material_key=self.material_key, strategy_fingerprint=self.strategy_fingerprint)
        if self.interpretation_ref != expected:
            raise InterpreterContractError("interpretation_ref is inconsistent")
        object.__setattr__(self, "started_at", _aware("started_at", self.started_at))
        object.__setattr__(self, "completed_at", _aware("completed_at", self.completed_at))
        if self.completed_at < self.started_at:
            raise InterpreterContractError("completed_at precedes started_at")
        object.__setattr__(self, "outcome", InterpretationOutcome(self.outcome))
        candidates = tuple(self.candidates)
        refs = {item.candidate_ref for item in candidates}
        if len(refs) != len(candidates):
            raise InterpreterContractError("candidate refs must be unique")
        for item in candidates:
            if not isinstance(item, (CandidateEntity, CandidateFact, CandidateRelation, CandidateConstraint)):
                raise InterpreterContractError("invalid candidate type")
            links = []
            if isinstance(item, CandidateFact):
                links = [item.subject_ref, item.condition_ref]
            elif isinstance(item, CandidateRelation):
                links = [item.subject_ref, item.object_ref, item.condition_ref]
            elif isinstance(item, CandidateConstraint):
                links = [item.subject_ref]
            if any(ref is not None and ref not in refs for ref in links):
                raise InterpreterContractError("candidate references unknown candidate")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "artifact_uses", tuple(self.artifact_uses))
        object.__setattr__(self, "warning_codes", tuple(dict.fromkeys(_code("warning_code", item) for item in self.warning_codes)))
        object.__setattr__(self, "failure_code", _text("failure_code", self.failure_code, optional=True, limit=120))
        if self.contract_version != 1:
            raise InterpreterContractError("unsupported interpreted material contract version")
        if self.outcome is InterpretationOutcome.FAILED and self.failure_code is None:
            raise InterpreterContractError("failed outcome requires failure_code")
        if self.outcome is not InterpretationOutcome.FAILED and self.failure_code is not None:
            raise InterpreterContractError("non-failed outcome cannot carry failure_code")
        if self.outcome is InterpretationOutcome.NO_USEFUL_INFORMATION and candidates:
            raise InterpreterContractError("no_useful_information cannot carry candidates")
        if self.outcome is InterpretationOutcome.INTERPRETED and not candidates:
            raise InterpreterContractError("interpreted requires candidates")


def candidate_payload(candidate):
    return {"kind": candidate.kind.value, **candidate.semantic_payload()}


def candidate_storage_payload(candidate):
    return {**candidate_payload(candidate), "candidate_ref": candidate.candidate_ref, "evidence": [e.to_payload() for e in candidate.evidence]}


def _evidence(payload):
    return CandidateEvidence(
        artifact_ref=payload.get("artifact_ref"),
        artifact_observation_ref=payload.get("artifact_observation_ref"),
        locator_kind=payload.get("locator_kind", "artifact"),
        locator=payload.get("locator"),
        extraction_method=payload.get("extraction_method", "artifact"),
        start_offset=payload.get("start_offset"),
        end_offset=payload.get("end_offset"),
        page_number=payload.get("page_number"),
    )


def candidate_from_storage_payload(payload):
    if not isinstance(payload, Mapping):
        raise InterpreterContractError("candidate payload must be a mapping")
    evidence = tuple(_evidence(item) for item in payload.get("evidence", ()))
    kind = CandidateKind(payload.get("kind"))
    common = {"candidate_ref": payload.get("candidate_ref"), "evidence": evidence}
    if kind is CandidateKind.ENTITY:
        return CandidateEntity(label=payload.get("label"), type_hints=tuple(payload.get("type_hints") or ()), language=payload.get("language"), **common)
    if kind is CandidateKind.FACT:
        return CandidateFact(subject_ref=payload.get("subject_ref"), predicate=payload.get("predicate"), value=CandidateValue.from_payload(payload.get("value") or {}), modality=payload.get("modality", "asserted"), condition_ref=payload.get("condition_ref"), **common)
    if kind is CandidateKind.RELATION:
        return CandidateRelation(subject_ref=payload.get("subject_ref"), predicate=payload.get("predicate"), object_ref=payload.get("object_ref"), modality=payload.get("modality", "asserted"), condition_ref=payload.get("condition_ref"), logic_group=payload.get("logic_group"), logic_operator=payload.get("logic_operator"), **common)
    return CandidateConstraint(subject_ref=payload.get("subject_ref"), predicate=payload.get("predicate"), operator=payload.get("operator"), value=CandidateValue.from_payload(payload.get("value") or {}), second_value=CandidateValue.from_payload(payload["second_value"]) if payload.get("second_value") else None, logic_group=payload.get("logic_group"), logic_operator=payload.get("logic_operator"), **common)


def strategy_fingerprint(components: Mapping[str, str]) -> str:
    if not isinstance(components, Mapping) or not components:
        raise InterpreterContractError("strategy components must be a non-empty mapping")
    normalized = {_code("component", str(k)): _text("version", str(v), limit=120) for k, v in components.items()}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def assign_candidate_ref(*, interpretation_ref: str, kind: CandidateKind, semantic_payload: Mapping):
    return make_candidate_ref(interpretation_ref=interpretation_ref, kind=CandidateKind(kind).value, payload=semantic_payload)
