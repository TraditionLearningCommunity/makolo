from __future__ import annotations

"""General deterministic semantics for Actor 3.

This module is deliberately domain-neutral.  It extracts a small interchange
vocabulary from already-observed document blocks; it never resolves canonical
Makolo objects and never fetches a URL.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from .contracts import (
    CandidateModality,
    CandidateValue,
    ConstraintOperator,
    LogicOperator,
)

_WS = re.compile(r"\s+")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NAMED_DATE = re.compile(
    r"^(?P<day>\d{1,2})\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December|"
    r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+(?P<year>\d{4})$",
    re.I,
)
_MONTHS = {
    "january": 1, "janvier": 1,
    "february": 2, "février": 2, "fevrier": 2,
    "march": 3, "mars": 3,
    "april": 4, "avril": 4,
    "may": 5, "mai": 5,
    "june": 6, "juin": 6,
    "july": 7, "juillet": 7,
    "august": 8, "août": 8, "aout": 8,
    "september": 9, "septembre": 9,
    "october": 10, "octobre": 10,
    "november": 11, "novembre": 11,
    "december": 12, "décembre": 12, "decembre": 12,
}
_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$",
    re.I,
)
_MONEY = re.compile(r"(?<!\w)(?P<number>\d+(?:[.,]\d+)?)\s*(?P<currency>[A-Z]{3})(?!\w)")
_QUANTITY = re.compile(
    r"(?<!\w)(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>"
    r"seconds?|minutes?|hours?|days?|weeks?|months?|years?|"
    r"secondes?|minutes?|heures?|jours?|semaines?|mois|ans?|"
    r"km|kilometers?|kilometres?|m|meters?|metres?|kg|g|"
    r"places?|seats?|slots?|tickets?|persons?|people|personnes?|"
    r"points?|percent|pourcent|%)\b",
    re.I,
)
_CAPACITY = re.compile(
    r"\b(?P<number>\d+)\s*(?P<unit>places?|seats?|slots?|tickets?|persons?|people|personnes?)\b",
    re.I,
)
_INTERVAL = re.compile(
    r"\b(?P<first>\d+(?:[.,]\d+)?)\s*(?:-|–|—|to|à|au)\s*"
    r"(?P<second>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-z%]+)?\b",
    re.I,
)
_THRESHOLD = re.compile(
    r"^(?P<label>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ._+/'-]{0,70}?)\s*"
    r"(?P<op>>=|<=|≥|≤|>|<|=|minimum|min\.?|maximum|max\.?)\s*"
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-z%]+)?$",
    re.I,
)
_EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_PHONE = re.compile(r"(?<!\w)(\+?\d[\d ()-]{6,}\d)(?!\w)")
_URL = re.compile(r"https?://[^\s<>()\"']+", re.I)

_REQUIREMENT_CONTEXT = re.compile(
    r"\b(requirements?|eligibility|eligible|prerequisites?|conditions?|criteria|admission|"
    r"exigences?|éligibilit[eé]|pr[eé]requis|conditions?|crit[eè]res?)\b",
    re.I,
)
_REQUIRED = re.compile(r"\b(required|must|mandatory|obligatoire|requis|exig[eé])\b", re.I)
_OPTIONAL = re.compile(r"\b(optional|facultatif|facultative)\b", re.I)
_RECOMMENDED = re.compile(r"\b(recommended|recommand[eé]e?)\b", re.I)
_PROHIBITED = re.compile(r"\b(prohibited|forbidden|interdit|interdite)\b", re.I)
_NEGATED = re.compile(r"\b(no|not|without|sans|aucun|aucune|ne\s+.+\s+pas)\b", re.I)
_CONDITION = re.compile(r"\b(?:only if|only for|if|when|provided that|si|lorsque|pour les)\s+(.+)$", re.I)

_LABELS = (
    (re.compile(r"^(?:deadline|application deadline|closing date|date limite|cl[oô]ture)\s*[:\-]\s*(.+)$", re.I), "deadline"),
    (re.compile(r"^(?:start|start date|starts?|d[eé]but|commence)\s*[:\-]\s*(.+)$", re.I), "start_date"),
    (re.compile(r"^(?:end|end date|ends?|fin)\s*[:\-]\s*(.+)$", re.I), "end_date"),
    (re.compile(r"^(?:duration|dur[eé]e)\s*[:\-]\s*(.+)$", re.I), "duration"),
    (re.compile(r"^(?:price|cost|fee|fees|prix|co[uû]t|frais)\s*[:\-]\s*(.+)$", re.I), "price"),
    (re.compile(r"^(?:capacity|seats?|places?|capacit[eé])\s*[:\-]\s*(.+)$", re.I), "capacity_announced"),
    (re.compile(r"^(?:location|place|venue|lieu|adresse)\s*[:\-]\s*(.+)$", re.I), "location_text"),
    (re.compile(r"^(?:origin|from|origine|d[eé]part)\s*[:\-]\s*(.+)$", re.I), "origin_text"),
    (re.compile(r"^(?:destination|to|arriv[eé]e)\s*[:\-]\s*(.+)$", re.I), "destination_text"),
    (re.compile(r"^(?:availability|available|disponibilit[eé]|disponible)\s*[:\-]\s*(.+)$", re.I), "availability"),
)

_ENTITY_LABELS = (
    (re.compile(r"^(?:organization|organisation|institution|provider|operator|university|universit[eé]|company|soci[eé]t[eé]|organisme)\s*[:\-]\s*(.+)$", re.I), "organization", "provided_by"),
    (re.compile(r"^(?:person|contact person|responsable|contact)\s*[:\-]\s*(.+)$", re.I), "person", "contact_person"),
    (re.compile(r"^(?:place|location|venue|city|ville|lieu)\s*[:\-]\s*(.+)$", re.I), "place", "located_at"),
)


def _clean(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def _decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    return number if number.is_finite() else None


def _unit(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9%]+", "_", value.lower()).strip("_")
    aliases = {
        "jour": "days", "jours": "days", "day": "days",
        "semaine": "weeks", "semaines": "weeks", "week": "weeks",
        "mois": "months", "month": "months",
        "an": "years", "ans": "years", "year": "years",
        "heure": "hours", "heures": "hours", "hour": "hours",
        "place": "seats", "places": "seats", "seat": "seats",
        "personne": "persons", "personnes": "persons", "people": "persons",
        "pourcent": "percent", "%": "percent",
    }
    return aliases.get(normalized, normalized)


def typed_value(raw: str, language: str | None = None) -> CandidateValue:
    raw = _clean(raw)
    money = _MONEY.fullmatch(raw)
    if money:
        return CandidateValue(
            kind="money",
            raw_text=raw,
            number=_decimal(money.group("number")),
            currency=money.group("currency").upper(),
            language=language,
        )
    quantity = _QUANTITY.fullmatch(raw)
    if quantity:
        return CandidateValue(
            kind="quantity",
            raw_text=raw,
            number=_decimal(quantity.group("number")),
            unit=_unit(quantity.group("unit")),
            language=language,
        )
    if _ISO_DATE.fullmatch(raw):
        try:
            from datetime import date
            return CandidateValue(kind="date", raw_text=raw, date_value=date.fromisoformat(raw), language=language)
        except ValueError:
            pass
    named = _NAMED_DATE.fullmatch(raw)
    if named:
        try:
            from datetime import date
            month = _MONTHS[named.group("month").casefold()]
            return CandidateValue(
                kind="date",
                raw_text=raw,
                date_value=date(int(named.group("year")), month, int(named.group("day"))),
                language=language,
            )
        except (KeyError, ValueError):
            pass
    if _ISO_DATETIME.fullmatch(raw):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if value.tzinfo is not None and value.utcoffset() is not None:
                return CandidateValue(
                    kind="datetime", raw_text=raw,
                    datetime_value=value.astimezone(timezone.utc), language=language,
                )
        except ValueError:
            pass
    number = _decimal(raw) if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", raw) else None
    if number is not None:
        return CandidateValue(kind="number", raw_text=raw, number=number, language=language)
    return CandidateValue(kind="text", raw_text=raw, text=raw, language=language)


def modality(text: str) -> CandidateModality:
    if _PROHIBITED.search(text):
        return CandidateModality.PROHIBITED
    if _OPTIONAL.search(text):
        return CandidateModality.OPTIONAL
    if _RECOMMENDED.search(text):
        return CandidateModality.RECOMMENDED
    if _NEGATED.search(text) and _REQUIRED.search(text):
        return CandidateModality.NEGATED
    if _REQUIRED.search(text):
        return CandidateModality.REQUIRED
    return CandidateModality.ASSERTED


def _logic_parts(text: str):
    if re.search(r"\s+(?:OR|OU)\s+", text, re.I):
        return LogicOperator.OR, re.split(r"\s+(?:OR|OU)\s+", text, flags=re.I)
    if re.search(r"\s+(?:AND|ET)\s+", text, re.I):
        return LogicOperator.AND, re.split(r"\s+(?:AND|ET)\s+", text, flags=re.I)
    return None, [text]


def _requirement(builder, subject_ref, block, text: str):
    text = _clean(text).strip("-•* ")
    if not text:
        return
    evidence = (block.evidence("generalist_rule"),)
    mode = modality(text)
    condition_ref = None
    conditional = _CONDITION.search(text)
    core = text
    if conditional:
        condition = _clean(conditional.group(1).strip(" .;"))
        if condition:
            condition_ref = builder.entity(
                condition[:300], type_hints=("condition_subject",),
                language=block.language, evidence=evidence,
            )
            mode = CandidateModality.CONDITIONAL
            core = _clean(text[:conditional.start()])
    core = re.sub(
        r"^(?:requirements?|eligibility|prerequisites?|conditions?|criteria|"
        r"exigences?|éligibilit[eé]|pr[eé]requis|conditions?|crit[eè]res?)\s*[:\-]\s*",
        "", core, flags=re.I,
    )
    core = re.sub(
        r"\b(?:is\s+)?(?:required|mandatory|requis|exig[eé]|obligatoire|optional|"
        r"recommended|recommand[eé]e?)\b",
        "", core, flags=re.I,
    )
    if mode is CandidateModality.NEGATED:
        core = re.sub(r"^(?:no|not|without|sans|aucun|aucune)\s+", "", core, flags=re.I)
    core = _clean(core.strip(" .;:"))
    if not core:
        return
    logic, parts = _logic_parts(core)
    group = None
    if logic:
        group = "logic-" + hashlib.sha256(
            f"{block.artifact_ref}:{block.locator}:{core}".encode()
        ).hexdigest()[:16]
    for part in parts:
        part = _clean(part.strip(" ,.;"))
        if not part:
            continue
        threshold = _THRESHOLD.fullmatch(part)
        if threshold:
            label = _clean(threshold.group("label"))
            ref = builder.entity(
                label[:300], type_hints=("requirement_subject",),
                language=block.language, evidence=evidence,
            )
            if subject_ref and ref != subject_ref:
                builder.relation(
                    subject_ref, "requires", ref, modality=mode,
                    condition_ref=condition_ref, logic_group=group,
                    logic_operator=logic, evidence=evidence,
                )
            unit = _unit(threshold.group("unit"))
            value = CandidateValue(
                kind="quantity" if unit else "number",
                raw_text=threshold.group("number"),
                number=_decimal(threshold.group("number")),
                unit=unit,
                language=block.language,
            )
            raw_op = threshold.group("op").lower()
            op = {
                ">=": ConstraintOperator.GTE, "≥": ConstraintOperator.GTE,
                "minimum": ConstraintOperator.GTE, "min": ConstraintOperator.GTE, "min.": ConstraintOperator.GTE,
                "<=": ConstraintOperator.LTE, "≤": ConstraintOperator.LTE,
                "maximum": ConstraintOperator.LTE, "max": ConstraintOperator.LTE, "max.": ConstraintOperator.LTE,
                ">": ConstraintOperator.GT, "<": ConstraintOperator.LT, "=": ConstraintOperator.EQ,
            }.get(raw_op, ConstraintOperator.EQ)
            predicate = "score" if unit in {None, "points", "percent"} else "threshold"
            builder.constraint(
                ref, predicate, op, value,
                logic_group=group, logic_operator=logic, evidence=evidence,
            )
            continue
        ref = builder.entity(
            part[:300], type_hints=("requirement_subject",),
            language=block.language, evidence=evidence,
        )
        if subject_ref and ref != subject_ref:
            builder.relation(
                subject_ref, "requires", ref, modality=mode,
                condition_ref=condition_ref, logic_group=group,
                logic_operator=logic, evidence=evidence,
            )


def extract_document_semantics(builder, document, subject_ref):
    """Add generic candidates from one SemanticDocument.

    The ResearchMission family is intentionally absent from this function: the
    observed document decides what is asserted.
    """
    for block in document.text_blocks:
        text = _clean(block.text)
        if not text:
            continue
        evidence = (block.evidence("generalist_rule"),)

        for pattern, predicate in _LABELS:
            match = pattern.match(text)
            if match:
                raw = _clean(match.group(1))
                value = typed_value(raw, block.language)
                if predicate in {"location_text", "origin_text", "destination_text", "availability"}:
                    value = CandidateValue(kind="text", raw_text=raw, text=raw, language=block.language)
                builder.fact(predicate, value, subject_ref=subject_ref, evidence=evidence)
                break

        for pattern, hint, predicate in _ENTITY_LABELS:
            match = pattern.match(text)
            if match:
                label = _clean(match.group(1))
                if label:
                    ref = builder.entity(label[:300], type_hints=(hint,), language=block.language, evidence=evidence)
                    if subject_ref and ref != subject_ref:
                        builder.relation(subject_ref, predicate, ref, evidence=evidence)

        heading = " ".join(block.heading_context)
        if _REQUIREMENT_CONTEXT.search(heading) or _REQUIREMENT_CONTEXT.match(text):
            if not re.fullmatch(r"[A-Za-zÀ-ÿ ]{1,40}:?", text) or block.kind in {"li", "dd", "p"}:
                _requirement(builder, subject_ref, block, text)

        interval = _INTERVAL.search(text)
        if interval and subject_ref:
            first = _decimal(interval.group("first"))
            second = _decimal(interval.group("second"))
            if first is not None and second is not None:
                unit = _unit(interval.group("unit")) or "number"
                if unit == "number":
                    first_value = CandidateValue(kind="number", raw_text=interval.group("first"), number=first, language=block.language)
                    second_value = CandidateValue(kind="number", raw_text=interval.group("second"), number=second, language=block.language)
                else:
                    first_value = CandidateValue(kind="quantity", raw_text=interval.group("first"), number=first, unit=unit, language=block.language)
                    second_value = CandidateValue(kind="quantity", raw_text=interval.group("second"), number=second, unit=unit, language=block.language)
                builder.constraint(
                    subject_ref, "range", ConstraintOperator.BETWEEN,
                    first_value, second_value=second_value, evidence=evidence,
                )

        capacity = _CAPACITY.search(text)
        if capacity and subject_ref:
            builder.fact(
                "capacity_announced",
                CandidateValue(
                    kind="quantity", raw_text=capacity.group(0),
                    number=Decimal(capacity.group("number")),
                    unit=_unit(capacity.group("unit")),
                    language=block.language,
                ),
                subject_ref=subject_ref, evidence=evidence,
            )

        for email in dict.fromkeys(_EMAIL.findall(text)):
            builder.fact(
                "contact_email",
                CandidateValue(kind="text", raw_text=email, text=email, language=block.language),
                subject_ref=subject_ref, evidence=evidence,
            )
        for phone in dict.fromkeys(_clean(v) for v in _PHONE.findall(text)):
            builder.fact(
                "contact_phone",
                CandidateValue(kind="text", raw_text=phone, text=phone, language=block.language),
                subject_ref=subject_ref, evidence=evidence,
            )

    for link in document.links:
        block = document.block_map().get(link.block_ref)
        if block is None:
            continue
        href = _clean(link.href)
        if not href:
            continue
        evidence = (block.evidence("document_link"),)
        lower = f"{link.text} {href}".lower()
        if href.lower().startswith("mailto:"):
            predicate, value = "contact_email", href[7:]
        elif href.lower().startswith("tel:"):
            predicate, value = "contact_phone", href[4:]
        elif re.search(r"\b(apply|application|candidature|candidate)\b", lower):
            predicate, value = "application_url", href
        elif re.search(r"\b(register|registration|inscription|reservation|book)\b", lower):
            predicate, value = "registration_url", href
        elif re.search(r"\b(contact)\b", lower):
            predicate, value = "contact_url", href
        elif "canonical" in link.rel or re.search(r"\b(guide|faq|rules?|r[eè]glement|form|pdf|documentation)\b", lower):
            predicate, value = "reference_url", href
        else:
            continue
        builder.fact(
            predicate,
            CandidateValue(kind="text", raw_text=value, text=value, language=block.language),
            subject_ref=subject_ref, evidence=evidence,
        )

    if document.forms and subject_ref:
        for block_ref in document.forms:
            block = document.block_map().get(block_ref)
            if block is None:
                continue
            builder.fact(
                "form_available",
                CandidateValue(kind="boolean", raw_text="true", boolean=True, language=block.language),
                subject_ref=subject_ref,
                evidence=(block.evidence("document_form"),),
            )
