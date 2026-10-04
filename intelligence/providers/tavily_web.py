from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Mapping

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest, IntelligenceResult
from intelligence.exceptions import (
    CapabilityUnsupported,
    InvalidProviderResult,
    ProviderUnavailable,
)
from intelligence.providers.base import IntelligenceProvider
from intelligence.providers.web_research_util import (
    mission_candidate_limit,
    mission_query,
    normalized_text,
    web_research_payload,
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_url(request, *, timeout):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


class TavilyWebResearchProvider(IntelligenceProvider):
    """Tavily Search adapter for the provider-neutral WEB_RESEARCH capability."""

    capabilities = frozenset({IntelligenceCapability.WEB_RESEARCH})

    def __init__(
        self,
        *,
        key: str,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 30,
    ):
        self.key = str(key).strip()
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key)
        self.timeout_seconds = max(int(timeout_seconds), 1)
        if not self.key or not self.base_url or not self.api_key:
            raise ValueError("Tavily Web Research provider configuration is incomplete")

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with _open_url(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderUnavailable("invalid_credentials") from exc
            if exc.code == 429:
                raise ProviderUnavailable("rate_limited") from exc
            raise ProviderUnavailable(f"http_{exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailable("network_unavailable") from exc

        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise InvalidProviderResult("invalid_json") from exc
        if not isinstance(value, dict):
            raise InvalidProviderResult("invalid_payload")
        return value

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        if request.capability is not IntelligenceCapability.WEB_RESEARCH:
            raise CapabilityUnsupported(request.capability.value)

        mission = web_research_payload(request)
        limit = mission_candidate_limit(mission, maximum=20)
        response = self._post(
            {
                "query": mission_query(mission),
                "search_depth": "basic",
                "max_results": limit,
                "topic": "general",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "auto_parameters": False,
            }
        )
        rows = response.get("results")
        if not isinstance(rows, list):
            raise InvalidProviderResult("tavily_results_invalid")

        sources = []
        candidates = []
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            url = row.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            url = url.strip()
            if url in seen:
                continue
            seen.add(url)
            title = normalized_text(row.get("title"), limit=1000)
            summary = normalized_text(row.get("content"))
            sources.append({"url": url, "title": title})
            candidates.append(
                {
                    "label": title or url,
                    "type_hints": [],
                    "summary": summary,
                    "source_urls": [url],
                }
            )

        stop_reason = (
            "no_new_candidates"
            if not candidates
            else "budget_exhausted"
            if len(candidates) >= limit
            else "completed"
        )
        return IntelligenceResult(
            available=True,
            output={
                "sources": sources,
                "candidates": candidates,
                "stop_reason": stop_reason,
            },
            provider_key=self.key,
        )
