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


def _verify_handoff(
    handoff: ObserverHandoff,
    *,
    target: ObservationTarget,
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
    }
    actual = {
        "target_key": handoff.target_key,
        "handoff_generation": handoff.handoff_generation,
        "locator": handoff.locator,
        "kind": handoff.kind,
        "requested_at": handoff.requested_at,
        "contract_version": handoff.contract_version,
        "observation_hints": handoff.observation_hints,
    }
    if actual != expected:
        raise ObserverStateConflictError(
            "existing observer handoff conflicts with idempotent replay"
        )


@transaction.atomic
def absorb_observation_target(
    target: ObservationTarget,
    *,
    absorbed_at: datetime | None = None,
) -> Tuple[ObserverHandoff, bool]:
    """Persist one accepted ObservationTarget without choosing a profile."""

    if not isinstance(target, ObservationTarget):
        raise ObserverContractError(
            "target must be an ObservationTarget"
        )
    absorbed_at = _aware(
        "absorbed_at",
        absorbed_at or timezone.now(),
    )
    hints = _json_mapping(
        "observation_hints",
        target.observation_hints,
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
            observation_hints=hints,
        )
        return existing, False

    try:
        # Keep the uniqueness race inside its own savepoint. Catching an
        # IntegrityError directly in the outer @atomic block would leave that
        # transaction marked for rollback and make the idempotent lookup below
        # unusable under real concurrent admission.
        with transaction.atomic():
            handoff = ObserverHandoff.objects.create(
                handoff_key=target.handoff_key,
                target_key=target.target_key,
                handoff_generation=target.handoff_generation,
                locator=target.locator,
                kind=target.kind,
                requested_at=target.requested_at,
                contract_version=target.contract_version,
                observation_hints=hints,
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
            observation_hints=hints,
        )
        return handoff, False
    return handoff, True


@transaction.atomic
def get_or_create_observation_series(
    target: ObservationTarget,
    *,
    profile_key: str,
    profile_fingerprint: str,
) -> Tuple[ObservationSeries, bool]:
    """Create Observer-owned longitudinal state for one comparable profile."""

    if not isinstance(target, ObservationTarget):
        raise ObserverContractError(
            "target must be an ObservationTarget"
        )
    profile_key = _required_text("profile_key", profile_key)
    profile_fingerprint = _required_text(
        "profile_fingerprint",
        profile_fingerprint,
    )
    series, created = ObservationSeries.objects.get_or_create(
        target_key=target.target_key,
        profile_fingerprint=profile_fingerprint,
        defaults={
            "kind": target.kind,
            "locator": target.locator,
            "profile_key": profile_key,
        },
    )
    if (
        series.kind != target.kind
        or series.locator != target.locator
        or series.profile_key != profile_key
    ):
        raise ObserverStateConflictError(
            "existing observation series conflicts with target/profile identity"
        )
    return series, created
