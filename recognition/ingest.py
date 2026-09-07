from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
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
        if value is None: continue
        if kind in NUMERIC_TYPES:
            try: number = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError) as exc: raise ValidationError({name: "Ce champ Signal doit être numérique."}) from exc
            if not number.is_finite(): raise ValidationError({name: "Ce champ Signal doit être fini."})
            normalized[name] = str(number)
        elif kind == BOOLEAN:
            if type(value) is not bool: raise ValidationError({name: "Ce champ Signal doit être booléen."})
            normalized[name] = value
        elif kind in {STRING, IDENTIFIER}:
            normalized[name] = str(value)[:255]
        else:
            raise ValidationError({name: "Type Signal Recognition inconnu."})
    return normalized


def _validate_contributors(contributors):
    safe = []
    for item in contributors or []:
        if not isinstance(item, dict): raise ValidationError("Un contributeur Recognition doit être déclaratif.")
        subject_type = item.get("subject_type"); subject_id = item.get("subject_id")
        if subject_type not in {"profile", "space"} or not subject_id: raise ValidationError("Un contributeur Recognition vise un Profile ou un Space explicite.")
        try: weight = Decimal(str(item.get("weight", item.get("share", 1))))
        except (InvalidOperation, TypeError, ValueError) as exc: raise ValidationError("Le poids d'un contributeur doit être numérique.") from exc
        if not weight.is_finite() or weight <= 0: raise ValidationError("Le poids d'un contributeur doit être fini et positif.")
        safe.append({"subject_type": subject_type, "subject_id": str(subject_id), "causal_mode": str(item.get("causal_mode", "operate"))[:20], "weight": str(weight)})
    return safe


def record_signal(*, signal_id, signal_kind, object_type, object_id, outcome_identity, occurred_at=None, available_at=None, values=None, contributors=None, confidence=Decimal("1"), source_ref=""):
    occurred_at = occurred_at or timezone.now(); available_at = available_at or timezone.now(); signal_kind = str(signal_kind)
    safe_values = _validate_values(signal_kind, values); safe_contributors = _validate_contributors(contributors)
    signal, created = RecognitionSignal.objects.get_or_create(
        signal_kind=signal_kind, outcome_identity=str(outcome_identity),
        defaults={"signal_id": str(signal_id), "object_type": str(object_type or "unknown")[:120], "object_id": str(object_id or "")[:160], "occurred_at": occurred_at, "available_at": available_at, "values": safe_values, "contributors": safe_contributors, "confidence": confidence, "source_ref": str(source_ref or "")[:255]},
    )
    if not created and signal.signal_id != str(signal_id): raise ValidationError("Cet outcome Recognition existe déjà avec une autre identité de Signal.")
    return signal
