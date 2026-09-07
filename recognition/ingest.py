from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from .models import RecognitionSignal
from .signal_contracts import BOOLEAN, IDENTIFIER, NUMERIC_TYPES, STRING, allowed_value_fields, field_type


def _validate_values(signal_kind, values):
    values = dict(values or {})
    allowed = allowed_value_fields(signal_kind)
    if not allowed:
        raise ValidationError("Ce type de Signal n'est pas exposé à Recognition.")
    unknown = set(values) - allowed
    if unknown:
        raise ValidationError(f"Champs Signal Recognition non autorisés: {', '.join(sorted(unknown))}.")
    normalized = {}
    for name, value in values.items():
        kind = field_type(signal_kind, name)
        if value is None:
            continue
        if kind in NUMERIC_TYPES:
            try:
                number = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError({name: "Ce champ Signal doit être numérique."}) from exc
            if not number.is_finite():
                raise ValidationError({name: "Ce champ Signal doit être fini."})
            normalized[name] = str(number)
        elif kind == BOOLEAN:
            if type(value) is not bool:
                raise ValidationError({name: "Ce champ Signal doit être booléen."})
            normalized[name] = value
        elif kind in {STRING, IDENTIFIER}:
            normalized[name] = str(value)[:255]
        else:
            raise ValidationError({name: "Type Signal Recognition inconnu."})
    return normalized


def _validate_contributors(contributors):
    safe = []
    for item in contributors or []:
        if not isinstance(item, dict):
            raise ValidationError("Un contributeur Recognition doit être déclaratif.")
        subject_type = item.get("subject_type")
        subject_id = item.get("subject_id")
        if subject_type not in {"profile", "space"} or not subject_id:
            raise ValidationError("Un contributeur Recognition vise un Profile ou un Space explicite.")
        try:
            weight = Decimal(str(item.get("weight", item.get("share", 1))))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Le poids d'un contributeur doit être numérique.") from exc
        if not weight.is_finite() or weight <= 0:
            raise ValidationError("Le poids d'un contributeur doit être fini et positif.")
        safe.append({
            "subject_type": subject_type,
            "subject_id": str(subject_id),
            "causal_mode": str(item.get("causal_mode", "operate"))[:20],
            "weight": str(weight),
        })
    # Attribution is set-like at ingestion; deterministic ordering makes retries
    # independent from producer list order without changing causal weights.
    safe.sort(key=lambda row: (row["subject_type"], row["subject_id"], row["causal_mode"], row["weight"]))
    return safe


def _semantic_collision(signal, expected):
    for field in (
        "signal_id", "object_type", "object_id", "occurred_at", "values",
        "contributors", "confidence", "source_ref",
    ):
        if getattr(signal, field) != expected[field]:
            return field
    return None


def record_signal(
    *, signal_id, signal_kind, object_type, object_id, outcome_identity,
    occurred_at=None, available_at=None, values=None, contributors=None,
    confidence=Decimal("1"), source_ref="",
):
    occurred_at = occurred_at or timezone.now()
    available_at = available_at or timezone.now()
    if available_at < occurred_at:
        raise ValidationError("available_at ne peut pas précéder occurred_at pour un Signal Recognition.")

    signal_kind = str(signal_kind)
    signal_id = str(signal_id)
    outcome_identity = str(outcome_identity)
    safe_values = _validate_values(signal_kind, values)
    safe_contributors = _validate_contributors(contributors)
    try:
        confidence = Decimal(str(confidence))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("La confiance Recognition doit être numérique.") from exc
    if not confidence.is_finite() or confidence < 0 or confidence > 1:
        raise ValidationError("La confiance Recognition doit être comprise entre 0 et 1.")

    expected = {
        "signal_id": signal_id,
        "object_type": str(object_type or "unknown")[:120],
        "object_id": str(object_id or "")[:160],
        "occurred_at": occurred_at,
        "values": safe_values,
        "contributors": safe_contributors,
        "confidence": confidence,
        "source_ref": str(source_ref or "")[:255],
    }

    existing_by_id = RecognitionSignal.objects.filter(signal_id=signal_id).first()
    if existing_by_id and (
        existing_by_id.signal_kind != signal_kind
        or existing_by_id.outcome_identity != outcome_identity
    ):
        raise ValidationError("Cette identité de Signal Recognition appartient déjà à un autre outcome.")

    try:
        signal, created = RecognitionSignal.objects.get_or_create(
            signal_kind=signal_kind,
            outcome_identity=outcome_identity,
            defaults={**expected, "available_at": available_at},
        )
    except IntegrityError as exc:
        existing_by_id = RecognitionSignal.objects.filter(signal_id=signal_id).first()
        if existing_by_id is not None:
            raise ValidationError("Cette identité de Signal Recognition appartient déjà à un autre outcome.") from exc
        raise

    if not created:
        collision = _semantic_collision(signal, expected)
        if collision:
            raise ValidationError(
                f"Retry Recognition incohérent sur {collision}: un outcome existant ne peut pas être réinterprété."
            )
        # available_at intentionally remains the first observation time. A retry
        # later must not move the fact into another scheduler window.
    return signal
