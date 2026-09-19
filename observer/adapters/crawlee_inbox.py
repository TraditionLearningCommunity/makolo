from __future__ import annotations

from datetime import datetime

from prospector.observation_contracts import ObservationTarget

from observer.errors import ObserverContractError

EXPECTED_LABEL = "makolo-observation"


def _required_text(name: str, value) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _requested_at(value) -> datetime:
    value = _required_text("requested_at", value)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ObserverContractError(
            "requested_at must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObserverContractError(
            "requested_at must be timezone-aware"
        )
    return parsed


def observation_target_from_crawlee_request(
    request,
) -> ObservationTarget:
    """Reconstruct the exact PX3 handoff from the Crawlee envelope."""

    if getattr(request, "label", None) != EXPECTED_LABEL:
        raise ObserverContractError(
            "unexpected Crawlee request label"
        )
    user_data = getattr(request, "user_data", None)
    if user_data is None or not hasattr(user_data, "__getitem__"):
        raise ObserverContractError(
            "Crawlee request user_data must support keyed access"
        )
    try:
        makolo = user_data["makolo"]
    except (KeyError, TypeError) as exc:
        raise ObserverContractError(
            "Crawlee request is missing makolo handoff data"
        ) from exc
    if not isinstance(makolo, dict):
        raise ObserverContractError(
            "Crawlee makolo handoff data must be a JSON object"
        )
    hints = makolo.get("observation_hints", {})
    if not isinstance(hints, dict):
        raise ObserverContractError(
            "observation_hints must be a mapping"
        )
    try:
        generation = int(makolo["handoff_generation"])
        contract_version = int(makolo["contract_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ObserverContractError(
            "invalid Crawlee handoff generation/version"
        ) from exc
    return ObservationTarget(
        handoff_key=_required_text(
            "handoff_key",
            makolo.get("handoff_key"),
        ),
        target_key=_required_text(
            "target_key",
            makolo.get("target_key"),
        ),
        handoff_generation=generation,
        locator=_required_text(
            "locator",
            makolo.get("locator"),
        ),
        kind=_required_text(
            "kind",
            makolo.get("kind"),
        ),
        requested_at=_requested_at(
            makolo.get("requested_at")
        ),
        observation_hints=hints,
        contract_version=contract_version,
    )
