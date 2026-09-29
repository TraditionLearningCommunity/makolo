from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Mapping
from urllib.parse import urlsplit

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest
from intelligence.gateway import IntelligenceGateway

from .evidence import EVIDENCE_FINDINGS_ATTRIBUTE

from .contracts import (
    WebResearchCandidate,
    WebResearchContractError,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_url(value: str) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return ""
    return value


class IntelligenceWebResearchEngine:
    """Run Web Research through the canonical IntelligenceGateway.

    The gateway remains responsible for capability routing, fallback, provider
    errors and privacy-safe telemetry. This class owns only translation between
    Makolo's Web Research contracts and IntelligenceRequest/Result.
    """

    def __init__(
        self,
        gateway: IntelligenceGateway,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.gateway = gateway
        self.clock = clock

    def _now(self) -> datetime:
        value = self.clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise WebResearchContractError("Web Research clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def execute(self, request: WebResearchRequest) -> WebResearchResult:
        if not isinstance(request, WebResearchRequest):
            raise WebResearchContractError("request must be a WebResearchRequest")

        started_at = self._now()
        intelligence_result = self.gateway.execute(
            IntelligenceRequest(
                capability=IntelligenceCapability.WEB_RESEARCH,
                input={"request": dict(request.to_payload())},
                metadata={
                    "feature": "web_research",
                    "request_ref": request.request_ref,
                },
            )
        )
        completed_at = self._now()

        if not intelligence_result.available:
            return WebResearchResult.from_request(
                request,
                started_at=started_at,
                completed_at=completed_at,
                outcome=WebResearchOutcome.FAILED,
                stop_reason=WebResearchStopReason.FAILED,
                failure_code=intelligence_result.reason or "provider_unavailable",
                engine_metadata={
                    "provider_key": intelligence_result.provider_key,
                    "model": intelligence_result.model,
                },
            )

        output = intelligence_result.output
        if not isinstance(output, Mapping):
            return WebResearchResult.from_request(
                request,
                started_at=started_at,
                completed_at=completed_at,
                outcome=WebResearchOutcome.FAILED,
                stop_reason=WebResearchStopReason.FAILED,
                failure_code="invalid_provider_output",
                engine_metadata={
                    "provider_key": intelligence_result.provider_key,
                    "model": intelligence_result.model,
                },
            )

        source_by_url = {}
        sources = []
        warnings = []
        for row in output.get("sources", ()):
            if not isinstance(row, Mapping):
                warnings.append("source_invalid")
                continue
            url = _canonical_url(row.get("url"))
            if not url or url in source_by_url:
                if not url:
                    warnings.append("source_invalid")
                continue
            try:
                source = WebResearchSource.from_locator(
                    locator=url,
                    observed_at=completed_at,
                    title=row.get("title") or None,
                )
            except WebResearchContractError:
                warnings.append("source_invalid")
                continue
            source_by_url[url] = source
            sources.append(source)

        candidates = []
        max_candidates = request.mission.limits.get("max_candidates")
        if (
            not isinstance(max_candidates, int)
            or isinstance(max_candidates, bool)
            or max_candidates < 1
        ):
            max_candidates = None

        for row in output.get("candidates", ()):
            if not isinstance(row, Mapping):
                warnings.append("candidate_invalid")
                continue
            urls = tuple(
                dict.fromkeys(
                    value.strip()
                    for value in tuple(row.get("source_urls") or ())
                    if isinstance(value, str) and value.strip()
                )
            )
            if not urls or any(url not in source_by_url for url in urls):
                warnings.append("candidate_unknown_source")
                continue

            finding_rows = []
            raw_findings = row.get("findings") or ()
            if not isinstance(raw_findings, (list, tuple)):
                warnings.append("evidence_findings_invalid")
                raw_findings = ()
            for finding in raw_findings:
                if not isinstance(finding, Mapping):
                    warnings.append("evidence_finding_invalid")
                    continue
                family = finding.get("family")
                predicate = finding.get("predicate")
                state = finding.get("state")
                value_text = finding.get("value_text")
                finding_urls = tuple(
                    dict.fromkeys(
                        value.strip()
                        for value in tuple(finding.get("source_urls") or ())
                        if isinstance(value, str) and value.strip()
                    )
                )
                if (
                    not isinstance(family, str)
                    or not family.strip()
                    or not isinstance(predicate, str)
                    or not predicate.strip()
                    or state not in {"observed", "unknown", "not_applicable"}
                    or not isinstance(value_text, str)
                ):
                    warnings.append("evidence_finding_invalid")
                    continue
                if any(
                    url not in source_by_url or url not in urls
                    for url in finding_urls
                ):
                    warnings.append("evidence_finding_unknown_source")
                    continue
                normalized_value = " ".join(value_text.split())
                if state == "observed" and (
                    not normalized_value or not finding_urls
                ):
                    warnings.append("evidence_finding_invalid")
                    continue
                if state == "not_applicable" and (
                    normalized_value or not finding_urls
                ):
                    warnings.append("evidence_finding_invalid")
                    continue
                if state == "unknown" and normalized_value:
                    warnings.append("evidence_finding_invalid")
                    continue
                finding_rows.append(
                    {
                        "family": family.strip(),
                        "predicate": predicate.strip(),
                        "state": state,
                        "value_text": normalized_value,
                        "source_refs": [
                            source_by_url[url].source_ref
                            for url in finding_urls
                        ],
                    }
                )

            attributes = {}
            if finding_rows:
                attributes[EVIDENCE_FINDINGS_ATTRIBUTE] = finding_rows
            try:
                candidate = WebResearchCandidate.build(
                    request_ref=request.request_ref,
                    label=row.get("label"),
                    source_refs=tuple(source_by_url[url].source_ref for url in urls),
                    type_hints=tuple(row.get("type_hints") or ()),
                    summary=row.get("summary") or None,
                    attributes=attributes,
                )
            except (TypeError, WebResearchContractError):
                warnings.append("candidate_invalid")
                continue
            candidates.append(candidate)

        candidate_limit_reached = (
            max_candidates is not None and len(candidates) > max_candidates
        )
        if candidate_limit_reached:
            candidates = candidates[:max_candidates]
            warnings.append("candidate_limit_reached")

        try:
            stop_reason = WebResearchStopReason(output.get("stop_reason"))
        except (TypeError, ValueError):
            return WebResearchResult.from_request(
                request,
                started_at=started_at,
                completed_at=completed_at,
                outcome=WebResearchOutcome.FAILED,
                stop_reason=WebResearchStopReason.FAILED,
                failure_code="invalid_stop_reason",
                sources=tuple(sources),
                warning_codes=tuple(warnings),
                engine_metadata={
                    "provider_key": intelligence_result.provider_key,
                    "model": intelligence_result.model,
                },
            )

        if candidate_limit_reached:
            stop_reason = WebResearchStopReason.BUDGET_EXHAUSTED

        if candidates:
            outcome = (
                WebResearchOutcome.PARTIAL
                if stop_reason
                in {
                    WebResearchStopReason.BUDGET_EXHAUSTED,
                    WebResearchStopReason.PROVIDER_LIMIT,
                    WebResearchStopReason.DEADLINE_REACHED,
                }
                else WebResearchOutcome.COMPLETED
            )
        else:
            outcome = WebResearchOutcome.NO_RESULTS
            if stop_reason is WebResearchStopReason.COMPLETED:
                stop_reason = WebResearchStopReason.NO_NEW_CANDIDATES

        return WebResearchResult.from_request(
            request,
            started_at=started_at,
            completed_at=completed_at,
            outcome=outcome,
            stop_reason=stop_reason,
            sources=tuple(sources),
            candidates=tuple(candidates),
            warning_codes=tuple(warnings),
            engine_metadata={
                "provider_key": intelligence_result.provider_key,
                "model": intelligence_result.model,
            },
        )
