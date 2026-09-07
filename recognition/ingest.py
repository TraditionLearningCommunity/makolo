from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import RecognitionSignal


def record_signal(*, signal_id, signal_kind, object_type, object_id, outcome_identity, occurred_at=None, available_at=None, values=None, contributors=None, confidence=Decimal("1"), source_ref=""):
    occurred_at = occurred_at or timezone.now()
    available_at = available_at or timezone.now()
    signal, created = RecognitionSignal.objects.get_or_create(
        signal_kind=str(signal_kind),
        outcome_identity=str(outcome_identity),
        defaults={
            "signal_id": str(signal_id),
            "object_type": str(object_type or "unknown")[:120],
            "object_id": str(object_id or "")[:160],
            "occurred_at": occurred_at,
            "available_at": available_at,
            "values": values or {},
            "contributors": contributors or [],
            "confidence": confidence,
            "source_ref": str(source_ref or "")[:255],
        },
    )
    if not created and signal.signal_id != str(signal_id):
        raise ValidationError("Cet outcome Recognition existe déjà avec une autre identité de Signal.")
    return signal
