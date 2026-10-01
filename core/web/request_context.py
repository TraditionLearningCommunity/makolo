from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Hashable
from uuid import uuid4

from django.utils import timezone


@dataclass
class MakoloRequestContext:
    """Small, non-persistent coordination context for one HTTP request."""

    request: object
    observed_at: object = field(default_factory=timezone.now)
    request_id: str = ""
    _memo: dict[Hashable, Any] = field(default_factory=dict, repr=False)
    _surface: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not self.request_id:
            incoming = getattr(self.request, "headers", {}).get("X-Request-ID", "").strip()
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", incoming):
                self.request_id = incoming
            else:
                self.request_id = uuid4().hex

    @property
    def surface(self):
        if self._surface is None:
            from .surface import surface_context_for_request
            self._surface = surface_context_for_request(self.request)
        return self._surface

    def memoize(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        if key not in self._memo:
            self._memo[key] = factory()
        return self._memo[key]


def get_request_context(request) -> MakoloRequestContext:
    context = getattr(request, "makolo", None)
    if context is None:
        context = MakoloRequestContext(request=request)
        request.makolo = context
    return context


def request_memoize(request, key: Hashable, factory: Callable[[], Any]) -> Any:
    return get_request_context(request).memoize(key, factory)


class MakoloRequestContextMiddleware:
    """Attach request-scoped coordination state without any database work."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.makolo = MakoloRequestContext(request=request)
        return self.get_response(request)
