from __future__ import annotations

from dataclasses import replace

from accounts.models import UserProfile
from geography.models import Place
from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest
from intelligence.gateway import IntelligenceGateway
from intelligence.runtime import build_runtime_registry

from .intent import AppliedConstraint, ConstraintSource, DiscoveryIntent


_ALLOWED_VERTICALS = {"event", "transport", "service", "other"}
_ALLOWED_WHEN = {"today", "tomorrow", "week", "weekend", "upcoming"}
_ALLOWED_PERIODS = {"morning", "afternoon", "evening"}
_ALLOWED_PRICE = {"free", "paid"}
_SYSTEM_PROMPT = (
    "Return one JSON object for Makolo discovery with only these string fields: "
    "vertical, place, when, period, price, text. "
    "Allowed values: vertical event|transport|service|other; "
    "when today|tomorrow|week|weekend|upcoming; "
    "period morning|afternoon|evening; price free|paid. "
    "Use empty strings when unknown and do not invent facts."
)
_STRUCTURED_KEYS = ("vertical", "place", "when", "period", "price")


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _canonical_place(value: str) -> str:
    value = _text(value)
    if not value:
        return ""
    name = Place.objects.filter(is_active=True, name__iexact=value).values_list("name", flat=True).first()
    if name:
        return name
    locality = Place.objects.filter(is_active=True, locality__iexact=value).values_list("locality", flat=True).first()
    return (locality or "").strip()


def _validate(output):
    if not isinstance(output, dict):
        return None
    raw_place = _text(output.get("place", ""))
    canonical_place = _canonical_place(raw_place)
    if raw_place and not canonical_place:
        return None
    values = {
        "vertical": _text(output.get("vertical")).lower(),
        "place": canonical_place,
        "when": _text(output.get("when")).lower(),
        "period": _text(output.get("period")).lower(),
        "price": _text(output.get("price")).lower(),
        "text": _text(output.get("text"))[:120],
    }
    if values["vertical"] and values["vertical"] not in _ALLOWED_VERTICALS:
        return None
    if values["when"] and values["when"] not in _ALLOWED_WHEN:
        return None
    if values["period"] and values["period"] not in _ALLOWED_PERIODS:
        return None
    if values["price"] and values["price"] not in _ALLOWED_PRICE:
        return None
    if values["period"] and values["when"] not in {"today", "tomorrow"}:
        return None
    if sum(bool(values[key]) for key in _STRUCTURED_KEYS) < 2:
        return None
    return values


def _constraints(values):
    labels = {
        "event": "Evenement",
        "transport": "Voyager",
        "service": "Service",
        "other": "Autre",
        "today": "Aujourd'hui",
        "tomorrow": "Demain",
        "week": "Cette semaine",
        "weekend": "Week-end",
        "upcoming": "A venir",
        "morning": "Matin",
        "afternoon": "Apres-midi",
        "evening": "Soir",
        "free": "Gratuit",
        "paid": "Payant",
    }
    result = []
    for key in _STRUCTURED_KEYS:
        value = values.get(key, "")
        if value:
            result.append(
                AppliedConstraint(
                    key,
                    value,
                    value if key == "place" else labels.get(value, value),
                    ConstraintSource.INTERPRETED,
                )
            )
    return tuple(result)


def _runtime_profile(principal):
    if isinstance(principal, UserProfile):
        return principal
    if not getattr(principal, "is_authenticated", False):
        return None
    return UserProfile.objects.filter(user=principal).first()


def _should_augment(intent: DiscoveryIntent) -> bool:
    if not intent.raw_text:
        return False
    if any(constraint.source == ConstraintSource.EXPLICIT for constraint in intent.constraints):
        return False
    if intent.constraints and not intent.text:
        return False
    return True


def _merge_candidate(intent: DiscoveryIntent, values):
    merged = {}
    for key in _STRUCTURED_KEYS:
        deterministic = getattr(intent, key)
        candidate = values[key]
        if deterministic and candidate and deterministic != candidate:
            return None
        merged[key] = deterministic or candidate
    if merged["period"] and merged["when"] not in {"today", "tomorrow"}:
        return None
    if sum(bool(merged[key]) for key in _STRUCTURED_KEYS) < 2:
        return None
    merged["text"] = values["text"]
    return merged


def interpret_with_intelligence(intent: DiscoveryIntent, *, profile=None, gateway=None) -> DiscoveryIntent:
    if not _should_augment(intent):
        return intent
    if gateway is None:
        registry = build_runtime_registry(
            capability=IntelligenceCapability.STRUCTURED_GENERATE,
            profile=_runtime_profile(profile),
        )
        gateway = IntelligenceGateway(registry=registry)
    request = IntelligenceRequest(
        capability=IntelligenceCapability.STRUCTURED_GENERATE,
        input={
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": intent.raw_text},
            ]
        },
        metadata={"feature": "discovery_interpret", "schema_version": 1},
    )
    result = gateway.execute(request)
    if not result.available:
        return intent
    values = _validate(result.output)
    if values is None:
        return intent
    merged = _merge_candidate(intent, values)
    if merged is None:
        return intent
    return replace(
        intent,
        text=merged["text"],
        vertical=merged["vertical"],
        place=merged["place"],
        when=merged["when"],
        period=merged["period"],
        price=merged["price"],
        constraints=_constraints(merged),
    )
