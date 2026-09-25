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