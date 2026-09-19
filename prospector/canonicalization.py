from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .errors import ProspectorContractError, UnsupportedTargetKindError

TARGET_KEY_VERSION = 1
WEB_URL_KIND = "web_url"


@dataclass(frozen=True, slots=True)
class CanonicalTarget:
    kind: str
    locator: str
    target_key: str


def _canonical_host(hostname: str) -> str:
    hostname = hostname.rstrip(".")
    if not hostname:
        raise ProspectorContractError("web_url hostname must not be empty")
    try:
        return ipaddress.ip_address(hostname).compressed.lower()
    except ValueError:
        try:
            return hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ProspectorContractError("web_url hostname is not valid IDNA") from exc


def canonicalize_web_url(locator: str) -> str:
    if not isinstance(locator, str):
        raise ProspectorContractError("locator must be a string")
    locator = locator.strip()
    if not locator:
        raise ProspectorContractError("locator must not be empty")

    try:
        parts = urlsplit(locator)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ProspectorContractError("web_url is malformed") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ProspectorContractError("web_url must use http or https")
    if not hostname:
        raise ProspectorContractError("web_url must be absolute and include a hostname")
    if parts.username is not None or parts.password is not None:
        raise ProspectorContractError("web_url must not contain embedded credentials")

    host = _canonical_host(hostname)
    rendered_host = f"[{host}]" if ":" in host else host
    default_port = 80 if scheme == "http" else 443
    netloc = rendered_host if port in {None, default_port} else f"{rendered_host}:{port}"

    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def canonicalize_locator(*, kind: str, locator: str) -> CanonicalTarget:
    normalized_kind = (kind or "").strip()
    if normalized_kind != WEB_URL_KIND:
        raise UnsupportedTargetKindError(
            f"no canonicalization contract registered for target kind {normalized_kind!r}"
        )

    canonical_locator = canonicalize_web_url(locator)
    payload = (normalized_kind + "\0" + canonical_locator).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return CanonicalTarget(
        kind=normalized_kind,
        locator=canonical_locator,
        target_key=f"{normalized_kind}:v{TARGET_KEY_VERSION}:{digest}",
    )
