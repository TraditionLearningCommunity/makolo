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


_WEB_RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "stop_reason": {
            "type": "string",
            "enum": [
                "completed",
                "coverage_saturated",
                "budget_exhausted",
                "no_new_candidates",
                "provider_limit",
                "deadline_reached",
            ],
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "type_hints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "summary": {"type": "string"},
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "family": {
                                    "type": "string",
                                    "enum": [
                                        "POSSIBILITY",
                                        "REQUIREMENT",
                                        "QUALIFICATION",
                                        "ACTOR",
                                        "SPATIOTEMPORAL",
                                        "PROCEDURE",
                                        "ECONOMIC",
                                        "REFERENCE",
                                    ],
                                },
                                "predicate": {"type": "string"},
                                "state": {
                                    "type": "string",
                                    "enum": [
                                        "observed",
                                        "unknown",
                                        "not_applicable",
                                    ],
                                },
                                "value_text": {"type": "string"},
                                "source_urls": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "family",
                                "predicate",
                                "state",
                                "value_text",
                                "source_urls",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "label",
                    "type_hints",
                    "summary",
                    "source_urls",
                    "findings",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["stop_reason", "candidates"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You are a Web research acquisition engine for Makolo.
Execute only the bounded research mission supplied by Makolo.
Search the Web broadly unless the mission itself contains an explicit scope.
Do not infer or inject a user's location, profile, preferences, or private context.
Do not recommend or rank candidates for a user.
Return only candidates supported by URLs actually consulted during this run.
For each candidate, return fact-level findings only when they answer the bounded mission.
Use observed only for a concise value explicitly supported by the cited consulted URLs.
Use unknown when the searched material did not establish the requested fact; keep value_text empty.
Never turn missing information into false, no restriction, closed, no fee, or any other assertion.
Use not_applicable only when consulted sources explicitly establish non-applicability.
If consulted sources disagree, emit separate observed findings with the same family and predicate and their respective values and source URLs; Makolo will classify the conflict.
Finding predicates are stable lowercase technical codes, not canonical Makolo field names or user relevance judgments.
A candidate source_urls list must contain every URL used by its findings and only URLs actually consulted during this run.
The response must match the supplied JSON schema exactly.
"""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_url(request, *, timeout):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _response_text(payload: Mapping) -> str:
    for item in payload.get("output", ()):
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        for content in item.get("content", ()):
            if (
                isinstance(content, Mapping)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                return content["text"]
    raise InvalidProviderResult("responses_output_text_missing")


def _source_records(payload: Mapping) -> tuple[dict[str, str], ...]:
    records = []
    seen = set()

    def admit(url, title=""):
        if not isinstance(url, str) or not url.strip():
            return
        url = url.strip()
        if url in seen:
            return
        seen.add(url)
        records.append(
            {
                "url": url,
                "title": title.strip() if isinstance(title, str) else "",
            }
        )

    for item in payload.get("output", ()):
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "web_search_call":
            action = item.get("action")
            if isinstance(action, Mapping):
                for source in action.get("sources", ()):
                    if isinstance(source, Mapping):
                        admit(source.get("url"), source.get("title", ""))
        if item.get("type") == "message":
            for content in item.get("content", ()):
                if not isinstance(content, Mapping):
                    continue
                for annotation in content.get("annotations", ()):
                    if not isinstance(annotation, Mapping):
                        continue
                    if annotation.get("type") != "url_citation":
                        continue
                    citation = annotation.get("url_citation")
                    if isinstance(citation, Mapping):
                        admit(citation.get("url"), citation.get("title", ""))
                    else:
                        admit(annotation.get("url"), annotation.get("title", ""))
    return tuple(records)


class OpenAIResponsesWebResearchProvider(IntelligenceProvider):
    """OpenAI Responses adapter for the provider-neutral WEB_RESEARCH capability.

    This adapter is intentionally not wired to persisted IntelligenceRoute rows
    in Phase 2. It can be registered in an IntelligenceRegistry explicitly,
    proving that Web Research can use the canonical gateway without forcing a
    provider/protocol migration.
    """

    capabilities = frozenset({IntelligenceCapability.WEB_RESEARCH})

    def __init__(
        self,
        *,
        key: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
    ):
        self.key = str(key).strip()
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key)
        self.model = str(model).strip()
        self.timeout_seconds = max(int(timeout_seconds), 1)
        if not self.key or not self.base_url or not self.api_key or not self.model:
            raise ValueError("OpenAI Web Research provider configuration is incomplete")

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}/responses",
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

        web_request = request.input.get("request")
        if not isinstance(web_request, Mapping):
            raise InvalidProviderResult("web_research_input_invalid")

        payload = {
            "model": self.model,
            "store": False,
            "tool_choice": "required",
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "input": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        web_request,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "makolo_web_research",
                    "strict": True,
                    "schema": _WEB_RESEARCH_SCHEMA,
                }
            },
        }

        mission = web_request.get("mission")
        limits = mission.get("limits") if isinstance(mission, Mapping) else None
        max_queries = limits.get("max_queries") if isinstance(limits, Mapping) else None
        if (
            isinstance(max_queries, int)
            and not isinstance(max_queries, bool)
            and max_queries > 0
        ):
            payload["max_tool_calls"] = max_queries

        response = self._post(payload)
        status = response.get("status")
        if status not in {None, "completed", "incomplete"}:
            raise InvalidProviderResult("responses_status_invalid")

        text = _response_text(response)
        try:
            structured = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise InvalidProviderResult("web_research_structured_output_invalid") from exc
        if not isinstance(structured, dict):
            raise InvalidProviderResult("web_research_structured_output_invalid")

        stop_reason = structured.get("stop_reason")
        candidates = structured.get("candidates")
        if stop_reason not in {
            "completed",
            "coverage_saturated",
            "budget_exhausted",
            "no_new_candidates",
            "provider_limit",
            "deadline_reached",
        }:
            raise InvalidProviderResult("web_research_stop_reason_invalid")
        if not isinstance(candidates, list):
            raise InvalidProviderResult("web_research_candidates_invalid")

        normalized_candidates = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise InvalidProviderResult("web_research_candidate_invalid")
            label = candidate.get("label")
            type_hints = candidate.get("type_hints")
            summary = candidate.get("summary")
            source_urls = candidate.get("source_urls")
            findings = candidate.get("findings")
            if (
                not isinstance(label, str)
                or not label.strip()
                or not isinstance(type_hints, list)
                or not all(isinstance(item, str) for item in type_hints)
                or not isinstance(summary, str)
                or not isinstance(source_urls, list)
                or not source_urls
                or not all(isinstance(item, str) and item.strip() for item in source_urls)
                or not isinstance(findings, list)
            ):
                raise InvalidProviderResult("web_research_candidate_invalid")

            normalized_findings = []
            for finding in findings:
                if not isinstance(finding, dict):
                    raise InvalidProviderResult("web_research_finding_invalid")
                family = finding.get("family")
                predicate = finding.get("predicate")
                finding_state = finding.get("state")
                value_text = finding.get("value_text")
                finding_urls = finding.get("source_urls")
                if (
                    family not in {
                        "POSSIBILITY",
                        "REQUIREMENT",
                        "QUALIFICATION",
                        "ACTOR",
                        "SPATIOTEMPORAL",
                        "PROCEDURE",
                        "ECONOMIC",
                        "REFERENCE",
                    }
                    or not isinstance(predicate, str)
                    or not predicate.strip()
                    or finding_state not in {
                        "observed",
                        "unknown",
                        "not_applicable",
                    }
                    or not isinstance(value_text, str)
                    or not isinstance(finding_urls, list)
                    or not all(
                        isinstance(item, str) and item.strip()
                        for item in finding_urls
                    )
                ):
                    raise InvalidProviderResult("web_research_finding_invalid")
                normalized_findings.append(
                    {
                        "family": family,
                        "predicate": predicate.strip(),
                        "state": finding_state,
                        "value_text": value_text.strip(),
                        "source_urls": [
                            item.strip() for item in finding_urls
                        ],
                    }
                )

            normalized_candidates.append(
                {
                    "label": label.strip(),
                    "type_hints": type_hints,
                    "summary": summary.strip(),
                    "source_urls": [item.strip() for item in source_urls],
                    "findings": normalized_findings,
                }
            )

        if status == "incomplete" and stop_reason in {
            "completed",
            "coverage_saturated",
            "no_new_candidates",
        }:
            stop_reason = "provider_limit"

        return IntelligenceResult(
            available=True,
            output={
                "sources": list(_source_records(response)),
                "candidates": normalized_candidates,
                "stop_reason": stop_reason,
            },
            provider_key=self.key,
            model=self.model,
        )
