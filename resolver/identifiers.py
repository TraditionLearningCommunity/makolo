from __future__ import annotations

import hashlib
import json

from .errors import ResolverContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ResolverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ResolverContractError(f"{name} must not be empty")
    return value


def make_resolution_ref(*, interpretation_ref: str, strategy_fingerprint: str) -> str:
    interpretation_ref = _required_text("interpretation_ref", interpretation_ref)
    strategy_fingerprint = _required_text("strategy_fingerprint", strategy_fingerprint)
    payload = f"{interpretation_ref}\0{strategy_fingerprint}".encode("utf-8")
    return "resolver:run:v1:" + hashlib.sha256(payload).hexdigest()


def make_assertion_ref(*, resolution_ref: str, kind: str, candidate_ref: str, payload) -> str:
    resolution_ref = _required_text("resolution_ref", resolution_ref)
    kind = _required_text("kind", kind)
    candidate_ref = _required_text("candidate_ref", candidate_ref)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(
        f"{resolution_ref}\0{kind}\0{candidate_ref}\0{canonical}".encode("utf-8")
    ).hexdigest()
    return "resolver:assertion:v1:" + digest


def make_provisional_ref(*, family: str, identity_key: str) -> str:
    family = _required_text("family", family).lower()
    identity_key = _required_text("identity_key", identity_key)
    digest = hashlib.sha256(f"{family}\0{identity_key}".encode("utf-8")).hexdigest()
    return f"resolver:provisional:v1:{family}:{digest}"


def strategy_fingerprint(components) -> str:
    if not isinstance(components, dict) or not components:
        raise ResolverContractError("strategy components must be a non-empty mapping")
    normalized = {}
    for key, value in components.items():
        k = _required_text("component", str(key)).lower()
        v = _required_text("component version", str(value))
        normalized[k] = v
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
