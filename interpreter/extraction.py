from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from io import BytesIO
import hashlib
import json
import re
from defusedxml import ElementTree

from observer.contracts import ArtifactCompleteness, ObservationOutcome

from .contracts import (
    ArtifactUse,
    CandidateConstraint,
    CandidateEntity,
    CandidateEvidence,
    CandidateFact,
    CandidateKind,
    CandidateModality,
    CandidateRelation,
    CandidateValue,
    CandidateValueKind,
    ConstraintOperator,
    EvidenceLocatorKind,
    InterpretedMaterial,
    InterpretationOutcome,
    LogicOperator,
    assign_candidate_ref,
    strategy_fingerprint,
)
from .documents import DOCUMENT_TYPES, DocumentLimitError, parse_html_document, parse_text_document
from .errors import MalformedContentError, ResourceLimitError, UnsupportedMediaError
from .generalist import extract_document_semantics, typed_value
from .identifiers import make_interpretation_ref

try:
    from pypdf import PdfReader
except ImportError:  # deployment check will expose a missing pinned dependency
    PdfReader = None

STRATEGY_KEY = "deterministic-first"
STRATEGY_VERSION = "2.1"
STRATEGY_COMPONENTS = {"document_structure": "2", "html": "2", "json": "1", "xml": "1", "text": "2", "pdf_text": "2", "generalist_semantics": "2", "intelligence_grounding": "1"}
STRATEGY_FINGERPRINT = strategy_fingerprint(STRATEGY_COMPONENTS)

MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_JSON_DEPTH = 64
MAX_XML_NODES = 25_000
MAX_PDF_PAGES = 128
MAX_CANDIDATES = 1000

_WS = re.compile(r"\s+")
_MONEY = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(USD|EUR|CDF|GBP|KES|ZAR)(?!\w)", re.I)
_QUANTITY = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(days?|jours?|weeks?|semaines?|months?|mois|years?|ans?|km|miles?|hours?|heures?|places?|seats?|points?)(?!\w)", re.I)
_DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre))\b", re.I)
_COMPARATOR = re.compile(
    r"\b(?P<label>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ._+/'-]{0,70}?)\s*"
    r"(?P<op>>=|≤|<=|≥|>|<|=|minimum|min\.?|maximum|max\.?)\s*"
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-z%]+)?\b",
    re.I,
)
_AGE = re.compile(r"\b(?:age|âge)\s*(?P<op><=|>=|<|>|maximum|minimum|max\.?|min\.?)\s*(?P<number>\d+)", re.I)
_CAPACITY = re.compile(r"\b(?P<number>\d+)\s*(?P<unit>places?|seats?)\b", re.I)


def _clean(value):
    return _WS.sub(" ", value or "").strip()


def _code(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")[:100] or "unknown"


def _media(descriptor):
    return (descriptor.detected_media_type or descriptor.declared_media_type or "").split(";", 1)[0].strip().lower() or None


def _decode(payload, descriptor):
    charset = (descriptor.charset or "utf-8").strip() or "utf-8"
    try:
        return payload.decode(charset), False
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace"), True


def _operator(raw):
    return {
        ">=": ConstraintOperator.GTE, "≥": ConstraintOperator.GTE, "minimum": ConstraintOperator.GTE, "min": ConstraintOperator.GTE, "min.": ConstraintOperator.GTE,
        "<=": ConstraintOperator.LTE, "≤": ConstraintOperator.LTE, "maximum": ConstraintOperator.LTE, "max": ConstraintOperator.LTE, "max.": ConstraintOperator.LTE,
        ">": ConstraintOperator.GT, "<": ConstraintOperator.LT, "=": ConstraintOperator.EQ,
    }.get(raw.strip().lower(), ConstraintOperator.EQ)


def _value(raw, language=None):
    return typed_value(str(raw), language)

def _hints(text):
    lower = re.sub(r"https?://\S+", " ", text.lower())
    result = []
    if re.search(r"\b(?:job|emploi|vacancy|recruitment)\b", lower):
        result.append("employment")
    if re.search(r"\b(?:course|training|formation|programme|program)\b", lower):
        result.append("activity")
    if re.search(r"\b(?:exam|assessment|test|examen)\b", lower):
        result.append("assessment")
    if re.search(r"\b(?:scholarship|bourse|grant|funding|financement)\b", lower):
        result.append("funding_program")
    return tuple(result)

def _modality(text):
    lower = text.lower()
    if re.search(r"\b(no|not|sans|aucun|aucune)\b.{0,25}\b(required|requis|exigé|obligatoire)\b", lower):
        return CandidateModality.NEGATED
    if re.search(r"\b(optional|facultatif|facultative)\b", lower):
        return CandidateModality.OPTIONAL
    if re.search(r"\b(recommended|recommandé|recommandée)\b", lower):
        return CandidateModality.RECOMMENDED
    if re.search(r"\b(prohibited|forbidden|interdit|interdite)\b", lower):
        return CandidateModality.PROHIBITED
    if re.search(r"\b(required|requirements?|requis|exigé|obligatoire|must)\b", lower):
        return CandidateModality.REQUIRED
    return CandidateModality.ASSERTED


def _evidence(descriptor, method, kind, locator=None, page=None):
    if page is None and kind is EvidenceLocatorKind.PDF_PAGE and locator:
        match = re.match(r"page:(\d+):", locator)
        if match:
            page = int(match.group(1))
    return CandidateEvidence(
        artifact_ref=descriptor.artifact_ref,
        artifact_observation_ref=descriptor.observation_ref,
        locator_kind=kind,
        locator=locator,
        extraction_method=method,
        page_number=page,
    )


class CandidateBuilder:
    def __init__(self, interpretation_ref):
        self.interpretation_ref = interpretation_ref
        self.items = {}

    def _put(self, probe):
        ref = assign_candidate_ref(interpretation_ref=self.interpretation_ref, kind=probe.kind, semantic_payload=probe.semantic_payload())
        candidate = replace(probe, candidate_ref=ref)
        previous = self.items.get(ref)
        if previous is not None:
            evidence = {json.dumps(e.to_payload(), sort_keys=True): e for e in previous.evidence}
            evidence.update({json.dumps(e.to_payload(), sort_keys=True): e for e in candidate.evidence})
            candidate = replace(previous, evidence=tuple(evidence.values()))
        elif len(self.items) >= MAX_CANDIDATES:
            raise ResourceLimitError("candidate limit exceeded")
        self.items[ref] = candidate
        return ref

    def entity(self, label, *, type_hints=(), language=None, evidence=()):
        return self._put(CandidateEntity("pending", _clean(label)[:2000], tuple(type_hints), language, tuple(evidence)))

    def fact(self, predicate, value, *, subject_ref=None, modality=CandidateModality.ASSERTED, condition_ref=None, evidence=()):
        return self._put(CandidateFact("pending", predicate, value, subject_ref, modality, condition_ref, tuple(evidence)))

    def relation(self, subject_ref, predicate, object_ref, *, modality=CandidateModality.ASSERTED, condition_ref=None, logic_group=None, logic_operator=None, evidence=()):
        return self._put(CandidateRelation("pending", subject_ref, predicate, object_ref, modality, condition_ref, logic_group, logic_operator, tuple(evidence)))

    def constraint(self, subject_ref, predicate, operator, value, *, second_value=None, logic_group=None, logic_operator=None, evidence=()):
        return self._put(CandidateConstraint("pending", subject_ref, predicate, operator, value, second_value, logic_group, logic_operator, tuple(evidence)))

    def ordered(self):
        order = {CandidateKind.ENTITY: 0, CandidateKind.FACT: 1, CandidateKind.RELATION: 2, CandidateKind.CONSTRAINT: 3}
        return tuple(sorted(self.items.values(), key=lambda item: (order[item.kind], item.candidate_ref)))


def _subject(builder, lines, descriptor, method, locator_kind, language=None):
    meaningful = [(p, _clean(t)) for p, t in lines if _clean(t)]
    if not meaningful:
        return None
    preferred = next(((p, t) for p, t in meaningful if "/h1[" in p), meaningful[0])
    label = preferred[1][:300]
    context = " ".join(t for _, t in meaningful[:20])
    hints = _hints(context)
    if len(meaningful) == 1 and not hints and not _COMPARATOR.search(label) and not _AGE.search(label):
        return None
    score = _COMPARATOR.search(label)
    if len(meaningful) == 1 and score:
        label = score.group("label").upper()
    return builder.entity(label, type_hints=hints, language=language, evidence=(_evidence(descriptor, method, locator_kind, preferred[0]),))


def _requirement(builder, subject_ref, text, descriptor, method, locator_kind, locator, language=None):
    text = _clean(text).strip("-•* ")
    if not text:
        return
    ev = (_evidence(descriptor, method, locator_kind, locator),)
    modality = _modality(text)
    condition_ref = None
    conditional = re.search(r"\b(?:only for|if|when|pour les|si)\s+(.+)$", text, re.I)
    core = text
    if conditional:
        condition = _clean(conditional.group(1).strip(" .;"))
        if condition:
            condition_ref = builder.entity(condition, type_hints=("condition_subject",), language=language, evidence=ev)
            modality = CandidateModality.CONDITIONAL
            core = _clean(text[:conditional.start()])
    core = re.sub(r"^(?:requirements?|prerequisites?|conditions?)\s*[:\-]\s*", "", core, flags=re.I)
    core = re.sub(r"\b(?:is\s+)?(?:required|requis|exigé|obligatoire|optional|recommended|recommandé)\b", "", core, flags=re.I)
    core = re.sub(r"^(?:no|not|sans)\s+", "", core, flags=re.I)
    core = _clean(core.strip(" .;:"))
    if not core:
        return
    logic = None
    if re.search(r"\s+(?:OR|OU)\s+", core, re.I):
        logic, parts = LogicOperator.OR, re.split(r"\s+(?:OR|OU)\s+", core, flags=re.I)
    elif re.search(r"\s+(?:AND|ET)\s+", core, re.I):
        logic, parts = LogicOperator.AND, re.split(r"\s+(?:AND|ET)\s+", core, flags=re.I)
    else:
        parts = [core]
    group = "logic-" + hashlib.sha256(f"{descriptor.artifact_ref}:{locator}:{core}".encode()).hexdigest()[:16] if logic else None
    for part in parts:
        part = _clean(part.strip(" ,.;"))
        if not part:
            continue
        score = _COMPARATOR.search(part)
        if score:
            ref = builder.entity(score.group("label").upper(), type_hints=("requirement_subject",), language=language, evidence=ev)
            if subject_ref and ref != subject_ref:
                builder.relation(subject_ref, "requires", ref, modality=modality, condition_ref=condition_ref, logic_group=group, logic_operator=logic, evidence=ev)
            builder.constraint(ref, "score", _operator(score.group("op")), CandidateValue(kind="number", raw_text=score.group("number"), number=Decimal(score.group("number").replace(",", ".")), language=language), logic_group=group, logic_operator=logic, evidence=ev)
            continue
        years = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:years?|ans?)\s+(?:of\s+)?(?:experience|expérience)", part, re.I)
        if years:
            ref = builder.entity("experience", type_hints=("experience",), language=language, evidence=ev)
            if subject_ref:
                builder.relation(subject_ref, "requires", ref, modality=modality, condition_ref=condition_ref, logic_group=group, logic_operator=logic, evidence=ev)
            builder.constraint(ref, "duration", ConstraintOperator.GTE, CandidateValue(kind="quantity", raw_text=years.group(0), number=Decimal(years.group(1).replace(",", ".")), unit="years", language=language), logic_group=group, logic_operator=logic, evidence=ev)
            continue
        ref = builder.entity(part[:300], type_hints=("requirement_subject",), language=language, evidence=ev)
        if subject_ref and ref != subject_ref:
            builder.relation(subject_ref, "requires", ref, modality=modality, condition_ref=condition_ref, logic_group=group, logic_operator=logic, evidence=ev)


def _semantic_lines(builder, subject_ref, lines, descriptor, method, locator_kind, language=None):
    cleaned = [(loc, _clean(text)) for loc, text in lines if _clean(text)]
    requirements = False
    consumed = set()
    for index, (locator, text) in enumerate(cleaned):
        if index in consumed:
            continue
        lower = text.lower()
        ev = (_evidence(descriptor, method, locator_kind, locator),)
        labelled = [
            (r"^(?:deadline|application deadline|closing date|date limite|clôture)\s*[:\-]\s*(.+)$", "deadline"),
            (r"^(?:start|start date|début|commence)\s*[:\-]\s*(.+)$", "start_date"),
            (r"^(?:end|end date|fin)\s*[:\-]\s*(.+)$", "end_date"),
            (r"^(?:duration|durée)\s*[:\-]\s*(.+)$", "duration"),
            (r"^(?:price|cost|fee|prix|coût|frais)\s*[:\-]\s*(.+)$", "price"),
            (r"^(?:location|place|lieu|adresse)\s*[:\-]\s*(.+)$", "location_text"),
        ]
        matched = False
        for pattern, predicate in labelled:
            found = re.match(pattern, text, re.I)
            if found:
                raw = found.group(1)
                value = CandidateValue(kind="text", raw_text=raw, text=raw, language=language) if predicate == "location_text" else _value(raw, language)
                builder.fact(predicate, value, subject_ref=subject_ref, evidence=ev)
                requirements = False
                matched = True
                break
        if matched:
            continue
        if re.match(r"^(?:requirements?|prerequisites?|conditions?)\s*:?$", text, re.I):
            requirements = True
            continue
        heading = re.match(r"^(deadline|start|duration|price|cost|fee|location|place|date limite|début|durée|prix|coût|frais|lieu|adresse)\s*:?$", text, re.I)
        if heading:
            requirements = False
            if index + 1 < len(cleaned):
                nloc, ntext = cleaned[index + 1]
                name = heading.group(1).lower()
                predicate = "deadline" if name in {"deadline", "date limite"} else "start_date" if name in {"start", "début"} else "duration" if name in {"duration", "durée"} else "price" if name in {"price", "cost", "fee", "prix", "coût", "frais"} else "location_text"
                nev = (_evidence(descriptor, method, locator_kind, nloc),)
                value = CandidateValue(kind="text", raw_text=ntext, text=ntext, language=language) if predicate == "location_text" else _value(ntext, language)
                builder.fact(predicate, value, subject_ref=subject_ref, evidence=nev)
                consumed.add(index + 1)
            continue
        if requirements:
            if text.endswith(":") and len(text.split()) <= 4:
                requirements = False
            else:
                _requirement(builder, subject_ref, text, descriptor, method, locator_kind, locator, language)
                continue
        if re.search(r"\b(?:required|mandatory|requis|exigé|obligatoire|optional|facultatif|recommended|recommandé)\b", lower):
            _requirement(builder, subject_ref, text, descriptor, method, locator_kind, locator, language)
            continue
        if _COMPARATOR.search(text):
            _requirement(builder, subject_ref, text, descriptor, method, locator_kind, locator, language)
        age = _AGE.search(text)
        if age and subject_ref:
            builder.constraint(subject_ref, "age", _operator(age.group("op")), CandidateValue(kind="quantity", raw_text=age.group(0), number=Decimal(age.group("number")), unit="years", language=language), evidence=ev)
        cap = _CAPACITY.search(text)
        if cap and subject_ref:
            builder.fact("capacity_announced", CandidateValue(kind="quantity", raw_text=cap.group(0), number=Decimal(cap.group("number")), unit=_code(cap.group("unit")), language=language), subject_ref=subject_ref, evidence=ev)
        if _MONEY.fullmatch(text) and subject_ref:
            builder.fact("price", _value(text, language), subject_ref=subject_ref, evidence=ev)
        if re.search(r"\b(?:covers?|funds?|finance|finances|couvre|prend en charge)\b", lower) and re.search(r"\b(?:fee|fees|frais|certification|test)\b", lower):
            target = re.sub(r"^.*?\b(?:covers?|funds?|finances?|couvre|prend en charge)\b", "", text, flags=re.I)
            target = re.sub(r"\b(?:for|pour)\b.*$", "", target, flags=re.I)
            ref = builder.entity(_clean(target.strip(" .;:"))[:300] or "fees", type_hints=("funded_resource",), language=language, evidence=ev)
            if subject_ref:
                builder.relation(subject_ref, "funds", ref, evidence=ev)
    if subject_ref and len(cleaned) <= 12:
        for index, (locator, text) in enumerate(cleaned[1:], 1):
            if index in consumed:
                continue
            ev = (_evidence(descriptor, method, locator_kind, locator),)
            if _DATE.fullmatch(text):
                builder.fact("mentioned_date", _value(text, language), subject_ref=subject_ref, evidence=ev)
            elif index <= 2 and len(text) <= 80 and not re.search(r"\d", text) and not text.endswith(":"):
                following = " ".join(t for _, t in cleaned[index + 1:index + 3])
                if (_DATE.search(following) or _MONEY.search(following)) and not re.search(r"\b(requirement|deadline|duration|price)\b", text, re.I):
                    builder.fact("location_text", CandidateValue(kind="text", raw_text=text, text=text, language=language), subject_ref=subject_ref, evidence=ev)


class HtmlCapture(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.counts = [{}]
        self.lines = []
        self.json_ld = []
        self.meta = []
        self.language = None
        self.json_depth = None
        self.json_path = None
        self.json_parts = []

    def path(self):
        return "/" + "/".join(f"{tag}[{index}]" for tag, index in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): v or "" for k, v in attrs}
        count = self.counts[-1].get(tag, 0) + 1
        self.counts[-1][tag] = count
        self.stack.append((tag, count))
        self.counts.append({})
        if tag == "html" and attrs.get("lang"):
            self.language = attrs["lang"].strip() or None
        if tag == "script" and "ld+json" in attrs.get("type", "").lower():
            self.json_depth, self.json_path, self.json_parts = len(self.stack), self.path(), []
        if tag == "meta":
            key, value = attrs.get("itemprop") or attrs.get("property") or attrs.get("name"), attrs.get("content")
            if key and value:
                self.meta.append((key, value))

    def handle_endtag(self, tag):
        if self.json_depth is not None and len(self.stack) == self.json_depth and self.stack and self.stack[-1][0] == "script":
            self.json_ld.append((self.json_path, "".join(self.json_parts).strip()))
            self.json_depth = self.json_path = None
            self.json_parts = []
        if self.stack:
            self.stack.pop()
            self.counts.pop()

    def handle_data(self, data):
        if self.json_depth is not None:
            self.json_parts.append(data)
            return
        if not self.stack or self.stack[-1][0] in {"script", "style", "noscript", "template"}:
            return
        text = _clean(data)
        if text:
            self.lines.append((self.path(), text))


def _json_depth(value, depth=0):
    if depth > MAX_JSON_DEPTH:
        raise ResourceLimitError("json nesting limit exceeded")
    if isinstance(value, dict):
        for child in value.values():
            _json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _json_depth(child, depth + 1)


def _structured_json(builder, value, descriptor, method, pointer="", subject_ref=None, language=None, preserve_document_subject=False, evidence_locator_kind=EvidenceLocatorKind.JSON_POINTER, evidence_locator=None):
    if isinstance(value, list):
        for i, child in enumerate(value):
            _structured_json(builder, child, descriptor, method, f"{pointer}/{i}", subject_ref, language, preserve_document_subject, evidence_locator_kind, evidence_locator)
        return
    if not isinstance(value, dict):
        return
    language = str(value.get("inLanguage") or language or "").strip() or None
    name = value.get("name") or value.get("headline") or value.get("title")
    type_value = value.get("@type") or value.get("type")
    hints = (_code(type_value),) if isinstance(type_value, str) else tuple(_code(v) for v in type_value if isinstance(v, str)) if isinstance(type_value, list) else ()
    locator = evidence_locator if evidence_locator is not None else (pointer or "/")
    ev = (_evidence(descriptor, method, evidence_locator_kind, locator),)
    document_declared = bool(set(hints).intersection(DOCUMENT_TYPES))
    if preserve_document_subject and document_declared and subject_ref:
        subject = subject_ref
    else:
        subject = builder.entity(name, type_hints=hints, language=language, evidence=ev) if isinstance(name, str) and _clean(name) else subject_ref
    mapping = {"startDate": "start_date", "endDate": "end_date", "datePublished": "publication_date", "validThrough": "deadline", "applicationDeadline": "deadline", "deadline": "deadline", "duration": "duration"}
    for key, predicate in mapping.items():
        raw = value.get(key)
        if raw is not None and not isinstance(raw, (dict, list)):
            builder.fact(predicate, _value(raw, language), subject_ref=subject, evidence=(_evidence(descriptor, method, evidence_locator_kind, evidence_locator if evidence_locator is not None else f"{pointer}/{key}"),))
    if value.get("price") is not None and not isinstance(value.get("price"), (dict, list)):
        raw = value["price"]
        if value.get("priceCurrency"):
            val = CandidateValue(kind="money", raw_text=f"{raw} {value['priceCurrency']}", number=Decimal(str(raw)), currency=str(value["priceCurrency"]), language=language)
        else:
            val = _value(raw, language)
        builder.fact("price", val, subject_ref=subject, evidence=ev)
    location = value.get("location") or value.get("jobLocation")
    if isinstance(location, str):
        builder.fact("location_text", CandidateValue(kind="text", raw_text=location, text=location, language=language), subject_ref=subject, evidence=ev)
    for key in ("qualifications", "skills", "experienceRequirements", "educationRequirements"):
        raw = value.get(key)
        if isinstance(raw, str):
            _requirement(builder, subject, raw, descriptor, method, evidence_locator_kind, evidence_locator if evidence_locator is not None else f"{pointer}/{key}", language)
        elif isinstance(raw, list):
            for i, item in enumerate(raw):
                if isinstance(item, str):
                    _requirement(builder, subject, item, descriptor, method, evidence_locator_kind, evidence_locator if evidence_locator is not None else f"{pointer}/{key}/{i}", language)
    for key, child in value.items():
        if isinstance(child, (dict, list)):
            _structured_json(builder, child, descriptor, method, f"{pointer}/{key}", subject, language, False, evidence_locator_kind, evidence_locator)


def _parse_html(builder, text, descriptor, semantic=True, intelligence_extractor=None, intelligence_stats=None):
    try:
        document = parse_html_document(text, descriptor)
    except DocumentLimitError as exc:
        raise ResourceLimitError(str(exc)) from exc
    except Exception as exc:
        raise MalformedContentError("html parser failure") from exc

    warnings = list(document.warning_codes)
    block_map = document.block_map()
    subject = None
    if semantic:
        preferred = next((b for b in document.blocks if b.kind == "title" and b.text), None)
        preferred = preferred or next((b for b in document.blocks if b.kind == "h1" and b.text), None)
        preferred = preferred or next(iter(document.text_blocks), None)
        if preferred:
            subject = builder.entity(
                (document.title or preferred.text)[:300],
                type_hints=("document",) + document.type_hints,
                language=document.language,
                evidence=(preferred.evidence("document_structure"),),
            )

    # Structured fragments are interpreted as claims inside the document. Their
    # declared schema type does not reclassify the document title as the thing
    # being mentioned.
    for fragment in document.structured_fragments:
        if fragment.kind != "json_ld" or not fragment.content:
            continue
        block = block_map.get(fragment.block_ref)
        if block is None:
            continue
        try:
            value = json.loads(fragment.content)
            _json_depth(value)
        except (json.JSONDecodeError, ResourceLimitError):
            if "malformed_json_ld" not in warnings:
                warnings.append("malformed_json_ld")
            continue
        _structured_json(
            builder, value, descriptor, "json_ld", block.locator,
            subject_ref=subject, language=document.language,
            preserve_document_subject=True,
            evidence_locator_kind=EvidenceLocatorKind.HTML_PATH,
            evidence_locator=block.locator,
        )

    for key, raw, block_ref in document.metadata:
        normalized = _code(key)
        predicate = {
            "startdate": "start_date", "enddate": "end_date",
            "datepublished": "publication_date", "article_published_time": "publication_date",
            "validthrough": "deadline", "deadline": "deadline", "price": "price",
        }.get(normalized)
        block = block_map.get(block_ref)
        if predicate and block:
            # itemprop describes the scoped item, not necessarily the document.
            fact_subject = None if block.attr("itemprop") else subject
            builder.fact(
                predicate, _value(raw, document.language), subject_ref=fact_subject,
                evidence=(block.evidence("html_meta"),),
            )

    if semantic:
        extract_document_semantics(builder, document, subject)
        lines = [(block.locator, block.text) for block in document.text_blocks]
        _semantic_lines(
            builder, subject, lines, descriptor, "document_structure",
            EvidenceLocatorKind.HTML_PATH, document.language,
        )
        if intelligence_extractor is not None:
            result = intelligence_extractor.extract(document, builder)
            if intelligence_stats is not None:
                intelligence_stats["calls"] += int(result.get("calls", 0))
                intelligence_stats["accepted"] += int(result.get("accepted", 0))
                intelligence_stats["rejected"] += int(result.get("rejected", 0))
                intelligence_stats["available"] = bool(
                    intelligence_stats.get("available") or result.get("available")
                )
    return warnings
def _parse_json(builder, text, descriptor):
    try:
        value = json.loads(text)
        _json_depth(value)
    except json.JSONDecodeError as exc:
        raise MalformedContentError("malformed json") from exc
    _structured_json(builder, value, descriptor, "json")


def _parse_xml(builder, text, descriptor):
    prefix = text[:4096].upper()
    if "<!DOCTYPE" in prefix or "<!ENTITY" in prefix:
        raise MalformedContentError("unsafe xml declaration")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise MalformedContentError("malformed xml") from exc
    nodes = list(root.iter())
    if len(nodes) > MAX_XML_NODES:
        raise ResourceLimitError("xml node limit exceeded")
    lines = []
    for i, elem in enumerate(nodes, 1):
        content = _clean(elem.text or "")
        if content:
            lines.append((f"/{str(elem.tag).rsplit('}', 1)[-1]}[{i}]", content))
    subject = _subject(builder, lines, descriptor, "xml", EvidenceLocatorKind.XML_PATH)
    _semantic_lines(builder, subject, lines, descriptor, "xml", EvidenceLocatorKind.XML_PATH)


def _parse_text(builder, text, descriptor, method="plain_text", page=None):
    try:
        document = parse_text_document(text, descriptor, page_number=page)
    except DocumentLimitError as exc:
        raise ResourceLimitError(str(exc)) from exc
    lines = [(block.locator, block.text) for block in document.text_blocks]
    kind = EvidenceLocatorKind.PDF_PAGE if page else EvidenceLocatorKind.TEXT_SPAN
    subject = _subject(builder, lines, descriptor, method, kind)
    extract_document_semantics(builder, document, subject)
    _semantic_lines(builder, subject, lines, descriptor, method, kind)


def _parse_pdf(builder, payload, descriptor):
    if PdfReader is None:
        raise UnsupportedMediaError("pdf parser unavailable")
    try:
        reader = PdfReader(BytesIO(payload), strict=False)
    except Exception as exc:
        raise MalformedContentError("malformed pdf") from exc
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ResourceLimitError("pdf page limit exceeded")
    pages = 0
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if _clean(text):
            pages += 1
            _parse_text(builder, text[:MAX_TEXT_CHARS], descriptor, "pdf_text", number)
    if not pages:
        raise MalformedContentError("pdf has no extractable text")
    return pages


def _artifacts(material):
    if material.outcome is ObservationOutcome.NOT_MODIFIED and material.revalidated_artifacts:
        return tuple(material.revalidated_artifacts)
    return tuple(material.artifacts or material.revalidated_artifacts)


def _primary_html(descriptors):
    for role in ("rendered_dom", "http_response_body", "browser_main_response_body"):
        matches = [d for d in descriptors if d.role == role and _media(d) in {"text/html", "application/xhtml+xml"}]
        if matches:
            return matches[-1].artifact_ref
    return None


class DeterministicInterpreter:
    strategy_key = STRATEGY_KEY
    strategy_version = STRATEGY_VERSION
    strategy_fingerprint = STRATEGY_FINGERPRINT

    def __init__(self, *, intelligence_extractor=None, strategy_fingerprint_override=None):
        self.intelligence_extractor = intelligence_extractor
        if strategy_fingerprint_override:
            self.strategy_fingerprint = strategy_fingerprint_override

    def interpret(self, material, artifact_reader, *, started_at, clock):
        interpretation_ref = make_interpretation_ref(material_key=material.material_key, strategy_fingerprint=self.strategy_fingerprint)
        descriptors = _artifacts(material)
        base_stats = {"bytes_read": 0, "artifacts_read": 0, "candidate_count": 0, "pdf_pages": 0, "llm_calls": 0, "intelligence_calls": 0, "intelligence_candidates_accepted": 0, "intelligence_candidates_rejected": 0, "ocr_calls": 0, "vision_calls": 0}
        if not descriptors:
            return InterpretedMaterial(
                interpretation_ref, material.material_key, material.observation_ref, material.target_key,
                self.strategy_key, self.strategy_version, self.strategy_fingerprint, started_at, clock(),
                InterpretationOutcome.FAILED, failure_code="insufficient_material",
            ), base_stats
        if sum(d.byte_length for d in descriptors) > MAX_TOTAL_BYTES:
            return InterpretedMaterial(
                interpretation_ref, material.material_key, material.observation_ref, material.target_key,
                self.strategy_key, self.strategy_version, self.strategy_fingerprint, started_at, clock(),
                InterpretationOutcome.FAILED, warning_codes=("source_too_large",), failure_code="resource_limit",
            ), base_stats

        builder = CandidateBuilder(interpretation_ref)
        primary_html = _primary_html(descriptors)
        warnings, uses = [], []
        success = failures = unsupported = bytes_read = pdf_pages = 0
        intelligence_stats = {"calls": 0, "accepted": 0, "rejected": 0, "available": False}
        supported = {"text/html", "application/xhtml+xml", "application/json", "application/ld+json", "application/xml", "text/xml", "application/rss+xml", "application/atom+xml", "text/plain", "text/csv", "application/pdf"}

        for descriptor in descriptors:
            media = _media(descriptor)
            if descriptor.byte_length > MAX_ARTIFACT_BYTES:
                warnings.append("artifact_too_large")
                failures += 1
                continue
            if descriptor.completeness is ArtifactCompleteness.TRUNCATED:
                warnings.append("source_truncated")
            elif descriptor.completeness is ArtifactCompleteness.INCOMPLETE:
                warnings.append("source_incomplete")
            if media not in supported and not (media and (media.endswith("+json") or media.endswith("+xml"))):
                warnings.append("unsupported_media")
                unsupported += 1
                continue
            try:
                payload = artifact_reader.read(descriptor.artifact_ref)
                bytes_read += len(payload)
                if len(payload) > MAX_ARTIFACT_BYTES:
                    raise ResourceLimitError("artifact exceeds byte limit")
                if media == "application/pdf":
                    pdf_pages += _parse_pdf(builder, payload, descriptor)
                    reason = "pdf_text"
                else:
                    text, replaced = _decode(payload, descriptor)
                    if replaced:
                        warnings.append("decode_replacement")
                    if len(text) > MAX_TEXT_CHARS:
                        text = text[:MAX_TEXT_CHARS]
                        warnings.append("text_truncated_by_interpreter")
                    if media in {"text/html", "application/xhtml+xml"}:
                        semantic = descriptor.artifact_ref == primary_html
                        warnings.extend(_parse_html(builder, text, descriptor, semantic, self.intelligence_extractor, intelligence_stats))
                        reason = "primary_rendered_html" if semantic and descriptor.role == "rendered_dom" else "primary_html" if semantic else "supplementary_structured_html"
                    elif media in {"application/json", "application/ld+json"} or media.endswith("+json"):
                        _parse_json(builder, text, descriptor)
                        reason = "structured_json"
                    elif media in {"application/xml", "text/xml", "application/rss+xml", "application/atom+xml"} or media.endswith("+xml"):
                        _parse_xml(builder, text, descriptor)
                        reason = "structured_xml"
                    else:
                        _parse_text(builder, text, descriptor)
                        reason = "plain_text"
                success += 1
                uses.append(ArtifactUse(descriptor.artifact_ref, descriptor.observation_ref, descriptor.role, media, descriptor.content_digest, reason, descriptor.completeness.value))
            except UnsupportedMediaError:
                warnings.append("unsupported_media")
                unsupported += 1
            except ResourceLimitError:
                warnings.append("resource_limit")
                failures += 1
            except MalformedContentError:
                warnings.append("malformed_content")
                failures += 1
            except Exception:
                warnings.append("parser_failure")
                failures += 1

        candidates = builder.ordered()
        warnings = tuple(dict.fromkeys(warnings))
        if not success:
            failure_code = "unsupported_media" if unsupported and not failures else "malformed_content" if "malformed_content" in warnings and "parser_failure" not in warnings else "resource_limit" if "resource_limit" in warnings else "parser_failure"
            outcome = InterpretationOutcome.FAILED
        elif not candidates:
            failure_code = None
            outcome = InterpretationOutcome.NO_USEFUL_INFORMATION
        elif failures or unsupported or any(w in warnings for w in ("source_truncated", "source_incomplete", "decode_replacement", "malformed_json_ld", "text_truncated_by_interpreter")):
            failure_code = None
            outcome = InterpretationOutcome.PARTIAL
        else:
            failure_code = None
            outcome = InterpretationOutcome.INTERPRETED

        output = InterpretedMaterial(
            interpretation_ref, material.material_key, material.observation_ref, material.target_key,
            self.strategy_key, self.strategy_version, self.strategy_fingerprint, started_at, clock(),
            outcome, candidates, tuple(uses), warnings, failure_code,
        )
        stats = {
            "bytes_read": bytes_read, "artifacts_read": success, "candidate_count": len(candidates),
            "artifact_count": len(descriptors), "parser_failures": failures, "unsupported_artifacts": unsupported,
            "pdf_pages": pdf_pages,
            "llm_calls": intelligence_stats["calls"],
            "intelligence_calls": intelligence_stats["calls"],
            "intelligence_candidates_accepted": intelligence_stats["accepted"],
            "intelligence_candidates_rejected": intelligence_stats["rejected"],
            "ocr_calls": 0, "vision_calls": 0,
        }
        return output, stats
