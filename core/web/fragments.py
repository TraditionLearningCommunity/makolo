from __future__ import annotations


def is_fragment_request(request, *, target: str | None = None) -> bool:
    """Return whether the request explicitly asks for an HTMX fragment."""
    if request.headers.get("HX-Request", "").lower() != "true":
        return False
    if target is None:
        return True
    return request.headers.get("HX-Target", "") == target
