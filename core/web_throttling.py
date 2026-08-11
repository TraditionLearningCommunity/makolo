import hashlib

from django.core.cache import cache


RATE_LIMIT_MESSAGE = "Trop de tentatives ont été reçues. Réessayez plus tard."


def _client_address(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR", "") or "unknown"


def _identity(value: str) -> str:
    return hashlib.sha256((value or "").strip().lower().encode("utf-8")).hexdigest()


def _increment(key: str, window_seconds: int) -> int:
    if cache.add(key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(key)
    except (ValueError, NotImplementedError):
        current = int(cache.get(key, 0) or 0) + 1
        cache.set(key, current, timeout=window_seconds)
        return current


def allow_web_request(
    request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identities: list[str] | None = None,
) -> bool:
    """Local-cache best-effort abuse protection for public web forms."""
    raw_identities = identities or [_client_address(request)]
    permitted = True
    for raw_identity in raw_identities:
        digest = _identity(raw_identity)
        key = f"makolo:web-throttle:{scope}:{digest}"
        if _increment(key, window_seconds) > limit:
            permitted = False
    return permitted


def client_rate_identity(request) -> str:
    return f"ip:{_client_address(request)}"


def value_rate_identity(prefix: str, value: str) -> str:
    return f"{prefix}:{(value or '').strip().lower()}"
