from __future__ import annotations

import hashlib
import json

from .errors import InterpreterContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise InterpreterContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise InterpreterContractError(f"{name} must not be empty")
    return value


def make_interpretation_ref(*, material_key: str, strategy_fingerprint: str) -> str:
    material_key = _required_text("material_key", material_key)
    strategy_fingerprint = _required_text(
        "strategy_fingerprint", strategy_fingerprint
    )
    payload = f"{material_key}\0{strategy_fingerprint}".encode("utf-8")
    return "interpreter:run:v1:" + hashlib.sha256(payload).hexdigest()


def make_candidate_ref(*, interpretation_ref: str, kind: str, payload) -> str:
    interpretation_ref = _required_text("interpretation_ref", interpretation_ref)
    kind = _required_text("kind", kind)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(
        f"{interpretation_ref}\0{kind}\0{canonical}".encode("utf-8")
    ).hexdigest()
    return f"interpreter:candidate:v1:{digest}"
