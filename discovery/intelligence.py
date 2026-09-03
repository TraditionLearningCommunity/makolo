from __future__ import annotations

from dataclasses import replace

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
    values = {
        "vertical": _text(output.get("vertical")).lower(),
        "place": _canonical_place(output.get("place", "")),
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
    if sum(bool(values[key]) for key in ("vertical", "place", "when", "period", "price")) < 2:
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
    for key in ("vertical", "place", "when", "period", "price"):
        value = values.get(key, "")
        if value:
            result.append(AppliedConstraint(key, value, value if key == "place" else labels.get(value, value), ConstraintSource.INTERPRETED))
    return tuple(result)


def interpret_with_intelligence(intent: DiscoveryIntent, *, profile=None, gateway=None) -> DiscoveryIntent:
    if not intent.raw_text or intent.constraints or intent.text != intent.raw_text:
        return intent
    if gateway is None:
        registry = build_runtime_registry(
            capability=IntelligenceCapability.STRUCTURED_GENERATE,
            profile=profile if getattr(profile, "is_authenticated", False) else None,
        )
        gateway = IntelligenceGateway(registry=registry)
    request = IntelligenceRequest(
        capability=IntelligenceCapability.STRUCTURED_GENERATE,
        input={"text": intent.raw_text},
        metadata={"feature": "discovery_interpret"},
    )
    result = gateway.execute(request)
    if not result.available:
        return intent
    values = _validate(result.output)
    if values is None:
        return intent
    return replace(
        intent,
        text=values["text"],
        vertical=values["vertical"],
        place=values["place"],
        when=values["when"],
        period=values["period"],
        price=values["price"],
        constraints=_constraints(values),
    )
