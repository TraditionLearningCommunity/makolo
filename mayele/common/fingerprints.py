from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .errors import MayeleContractError


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise MayeleContractError("datetime values must be timezone-aware")
        return value.isoformat()
    if is_dataclass(value):
        return _canonicalize(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise MayeleContractError(
        f"unsupported semantic fingerprint value: {type(value).__name__}"
    )


def canonical_json(value: Any) -> str:
    """Serialize semantic content deterministically."""

    try:
        return json.dumps(
            _canonicalize(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise MayeleContractError("value is not canonical JSON") from exc


def semantic_fingerprint(value: Any) -> str:
    """Return a deterministic SHA-256 semantic fingerprint."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
