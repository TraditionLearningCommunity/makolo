from __future__ import annotations

import hashlib
import json
import re
import unicodedata

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w]+", re.UNICODE)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = _PUNCT.sub(" ", value)
    return _WS.sub(" ", value).strip()


def normalized_hostname(url: str | None) -> str | None:
    if not url:
        return None
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url).hostname or "").encode("idna").decode("ascii").lower() or None
    except (UnicodeError, ValueError):
        return None


def semantic_fingerprint(payload) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def endpoint_key(endpoint) -> str:
    if endpoint is None:
        return ""
    if endpoint.kind.value == "canonical":
        return f"canonical:{endpoint.canonical_ref.domain}:{endpoint.canonical_ref.object_ref}"
    return f"{endpoint.kind.value}:{endpoint.ref}"
