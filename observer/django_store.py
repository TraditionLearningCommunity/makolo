from __future__ import annotations

import json
from datetime import datetime
from typing import Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from prospector.observation_contracts import ObservationTarget

from .django_app.models import ObservationSeries, ObserverHandoff
from .errors import ObserverContractError, ObserverStateConflictError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value


def _json_mapping(name: str, value) -> dict:
    if not isinstance(value, dict) and not hasattr(value, "items"):
        raise ObserverContractError(f"{name} must be a mapping")
    data = dict(value)
    try:
        json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ObserverContractError(
            f"{name} must be JSON-serializable"
        ) from exc
    return data


def _verify_series(
    series: ObservationSeries,
    *,
    target: ObservationTarget,
    profile_key: str,
) -> None:
    if (
        series.target_key != target.target_key
        or series.kind != target.kind
        or series.locator != target.locator
        or series.profile_key != profile_key
    ):
        raise ObserverStateConflictError(
            "existing observation series conflicts with target/profile identity"
        )


def _verify_handoff(
    handoff: ObserverHandoff,
    *,
    target: ObservationTarget,
    series: ObservationSeries,
    observation_hints: dict,
) -> None:
    expected = {
        "target_key": target.target_key,
        "handoff_generation": target.handoff_generation,
        "locator": target.locator,
        "kind": target.kind,
        "requested_at": target.requested_at,
        "contract_version": target.contract_version,
        "observation_hints": observation_hints,
        "series_id": series.pk,
    }
    actual = {
        "target_key": handoff.target_key,
        "handoff_generation": handoff.handoff_generation,
        "locator": handoff.locator,
        "kind": handoff.kind,
        "requested_at": handoff.requested_at,
        "contract_version": handoff.contract_version,
        "observation_hints": handoff.observation_hints,
        "series_id": handoff.series_id,
    }
    if actual != expected:
        raise ObserverStateConflictError(
            "existing observer handoff conflicts with idempotent replay"
        )


@transaction.atomic
def absorb_observation_target(
    target: ObservationTarget,
    *,
    profile_key: str,
    profile_fingerprint: str,
    absorbed_at: datetime | None = None,
) -> Tuple[ObserverHandoff, bool]:
    """Persist one accepted ObservationTarget without creating an Observation."""

    if not isinstance(target, ObservationTarget):
        raise ObserverContractError(
            "target must be an ObservationTarget"
        )
    profile_key = _required_text("profile_key", profile_key)
    profile_fingerprint = _required_text(
        "profile_fingerprint",
        profile_fingerprint,
    )
    absorbed_at = _aware(
        "absorbed_at",
        absorbed_at or timezone.now(),
    )
    hints = _json_mapping(
        "observation_hints",
        target.observation_hints,
    )

    series, _created = ObservationSeries.objects.get_or_create(
        target_key=target.target_key,
        profile_fingerprint=profile_fingerprint,
        defaults={
            "kind": target.kind,
            "locator": target.locator,
            "profile_key": profile_key,
        },
    )
    _verify_series(
        series,
        target=target,
        profile_key=profile_key,
    )

    existing = (
        ObserverHandoff.objects.filter(
            handoff_key=target.handoff_key
        ).first()
        or ObserverHandoff.objects.filter(
            target_key=target.target_key,
            handoff_generation=target.handoff_generation,
        ).first()
    )
    if existing is not None:
        _verify_handoff(
            existing,
            target=target,
            series=series,
            observation_hints=hints,
        )
        return existing, False

    try:
        handoff = ObserverHandoff.objects.create(
            handoff_key=target.handoff_key,
            target_key=target.target_key,
            handoff_generation=target.handoff_generation,
            locator=target.locator,
            kind=target.kind,
            requested_at=target.requested_at,
            contract_version=target.contract_version,
            observation_hints=hints,
            series=series,
            absorbed_at=absorbed_at,
        )
    except IntegrityError:
        handoff = (
            ObserverHandoff.objects.filter(
                handoff_key=target.handoff_key
            ).first()
            or ObserverHandoff.objects.filter(
                target_key=target.target_key,
                handoff_generation=target.handoff_generation,
            ).first()
        )
        if handoff is None:
            raise
        _verify_handoff(
            handoff,
            target=target,
            series=series,
            observation_hints=hints,
        )
        return handoff, False
    return handoff, True
