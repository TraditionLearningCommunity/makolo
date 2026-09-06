from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse


class WebhookError(RuntimeError):
    pass


class WebhookAuthenticationError(WebhookError):
    pass


class WebhookReplayError(WebhookAuthenticationError):
    pass


class WebhookDeliveryError(WebhookError):
    pass


def _validate_outbound_endpoint(value: str) -> None:
    """Reject obviously unsafe webhook targets before transport execution.

    M7 deliberately does not perform DNS resolution here. The transport/network
    layer remains responsible for redirect and DNS-rebinding protections, while
    this contract prevents direct localhost/private/reserved literal targets.
    """

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme != "https" or not hostname:
        raise ValueError("Outbound webhook endpoint must use a public HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("Outbound webhook endpoint must not contain URL credentials.")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Outbound webhook endpoint must not target localhost.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Outbound webhook endpoint must not target a private, local or reserved address.")


@dataclass(frozen=True, slots=True)
class WebhookSubscription:
    """Code/configuration-defined outbound subscription.

    Only a key reference is retained here. Secret resolution is injected by the
    runtime; M7 does not introduce a second credential store.
    """

    code: str
    endpoint_url: str
    event_types: frozenset[str]
    signing_key_id: str
    payload_builder: Callable[[Any], Mapping[str, Any]]
    allow_event: Callable[[Any], bool]

    def __init__(
        self,
        *,
        code: str,
        endpoint_url: str,
        event_types: Iterable[str],
        signing_key_id: str,
        payload_builder: Callable[[Any], Mapping[str, Any]],
        allow_event: Callable[[Any], bool],
    ) -> None:
        code = code.strip()
        endpoint_url = endpoint_url.strip()
        signing_key_id = signing_key_id.strip()
        normalized_events = frozenset(item.strip() for item in event_types if item.strip())
        if not code or not endpoint_url or not signing_key_id or not normalized_events:
            raise ValueError("Webhook subscription requires code, endpoint, events and signing key reference.")
        if not callable(payload_builder) or not callable(allow_event):
            raise ValueError("Webhook payload builder and visibility policy must be callable.")
        _validate_outbound_endpoint(endpoint_url)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "endpoint_url", endpoint_url)
        object.__setattr__(self, "event_types", normalized_events)
        object.__setattr__(self, "signing_key_id", signing_key_id)
        object.__setattr__(self, "payload_builder", payload_builder)
        object.__setattr__(self, "allow_event", allow_event)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def sign_webhook(*, secret: str, timestamp: int, body: bytes) -> str:
    if not secret:
        raise WebhookAuthenticationError("Webhook signing secret is unavailable.")
    signed = str(int(timestamp)).encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def verify_webhook(
    *,
    secret: str,
    timestamp: int,
    body: bytes,
    signature: str,
    replay_key: str,
    claim_replay_key: Callable[[str], bool],
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> None:
    now = int(time.time() if now is None else now)
    timestamp = int(timestamp)
    if abs(now - timestamp) > tolerance_seconds:
        raise WebhookAuthenticationError("Webhook timestamp is outside the accepted window.")
    expected = sign_webhook(secret=secret, timestamp=timestamp, body=body)
    if not hmac.compare_digest(expected, signature or ""):
        raise WebhookAuthenticationError("Webhook signature is invalid.")
    if not replay_key or not claim_replay_key(replay_key):
        raise WebhookReplayError("Webhook replay detected.")


def deliver_domain_event(
    *,
    subscription: WebhookSubscription,
    event: Any,
    resolve_secret: Callable[[str], str],
    transport: Callable[[str, bytes, Mapping[str, str]], Any],
    timestamp: int | None = None,
) -> Any:
    if getattr(event, "event_type", None) not in subscription.event_types:
        return None
    if not subscription.allow_event(event):
        return None

    payload = dict(subscription.payload_builder(event))
    body = canonical_json_bytes(payload)
    timestamp = int(time.time() if timestamp is None else timestamp)
    secret = resolve_secret(subscription.signing_key_id)
    signature = sign_webhook(secret=secret, timestamp=timestamp, body=body)
    headers = {
        "Content-Type": "application/json",
        "X-Makolo-Webhook-Timestamp": str(timestamp),
        "X-Makolo-Webhook-Signature": signature,
    }
    try:
        return transport(subscription.endpoint_url, body, headers)
    except Exception as exc:
        raise WebhookDeliveryError("Webhook transport failed.") from exc
