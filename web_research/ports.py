from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import WebResearchRequest, WebResearchResult


@runtime_checkable
class WebResearchEnginePort(Protocol):
    """Provider-neutral execution boundary for one bounded Web Research request."""

    def execute(self, request: WebResearchRequest) -> WebResearchResult:
        ...
