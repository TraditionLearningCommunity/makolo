"""User-invoked, owner-scoped clarification of a Discovery search.

No free-form chat, factual invention or new Action registry. The result only
contains bounded Discovery criteria; Discovery remains the search owner.
"""
from __future__ import annotations

import logging

from accounts.models import UserProfile
from intelligence.capabilities import IntelligenceCapability
from intelligence.gateway import IntelligenceGateway
from intelligence.runtime import build_runtime_registry

from .intent import resolve_discovery_intent
from .intelligence import interpret_with_intelligence, _should_augment


_logger = logging.getLogger("makolo.discovery")


def _record_external_action(*, action: str, status: str, reason: str = "",
                            candidates: int = 0) -> None:
    """Safe operational event. Never include search text, user, key or URL."""
    public_reason = reason if reason in {
        "invalid_credentials", "rate_limited", "network_unavailable",
        "connection_unavailable", "provider_unavailable",
    } else ""
    _logger.info(
        "discovery.external_action",
        extra={
            "makolo_event": "discovery.external_action",
            "action": action,
            "status": status,
            "reason": public_reason,
            "candidate_count": max(0, min(int(candidates), 3)),
        },
    )


_ALLOWED_CRITERIA = frozenset({
    "q", "place", "when", "period", "vertical", "price",
    "date", "date_from", "date_to", "timezone",
    "lat", "lon", "radius_km",
})


def _public_failure(reason: str) -> str:
    """Closed vocabulary for UI and logs; never forward provider messages."""
    if reason in {
        "invalid_credentials", "rate_limited", "network_unavailable",
        "connection_unavailable",
    }:
        return reason
    if reason == "capability_not_configured":
        return "connection_unavailable"
    return "provider_unavailable"


class _ObservedGateway:
    """Observe one explicit action, without storing its provider output."""
    def __init__(self, gateway):
        self.gateway = gateway
        self.failure = ""

    def execute(self, request):
        result = self.gateway.execute(request)
        if not result.available:
            self.failure = _public_failure(result.reason)
        return result


def clarify_discovery_search(*, actor, criteria: dict) -> dict:
    """Explicit action, with no client-selected provider/owner or persistent effect."""
    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Authentification requise.")
    if not isinstance(criteria, dict) or set(criteria) - _ALLOWED_CRITERIA:
        raise ValueError("Critères non autorisés.")
    if not all(isinstance(value, str) for value in criteria.values()):
        raise ValueError("Critères invalides.")
    if any(len(value) > (120 if key == "q" else 160) for key, value in criteria.items()):
        raise ValueError("Critères trop longs.")
    params = {key: value.strip() for key, value in criteria.items()}
    intent = resolve_discovery_intent(params)
    status = "already_structured"
    reason = ""
    if _should_augment(intent) and not any(
        value for key, value in params.items() if key not in {"q", "radius_km"}
    ):
        profile = UserProfile.objects.filter(user=actor).first()
        registry = build_runtime_registry(
            capability=IntelligenceCapability.STRUCTURED_GENERATE,
            profile=profile,
        )
        if not registry.providers_for(IntelligenceCapability.STRUCTURED_GENERATE):
            status = "unavailable"
            reason = "connection_unavailable"
        else:
            observer = _ObservedGateway(IntelligenceGateway(registry=registry))
            try:
                enriched = interpret_with_intelligence(
                    intent, gateway=observer,
                )
            except Exception:
                # No provider exception or credential details reach the client.
                enriched = intent
                observer.failure = "provider_unavailable"
            status = ("unavailable" if observer.failure else
                      "applied" if enriched != intent else "unchanged")
            reason = observer.failure
            intent = enriched
    elif not intent.raw_text:
        status = "empty"
    _record_external_action(action="clarify", status=status, reason=reason)
    return {
        "status": status,
        "reason": reason,
        "query": intent.to_search_params(),
        "constraints": [
            {
                "key": constraint.key,
                "value": constraint.value,
                "label": constraint.label,
                "source": constraint.source.value,
            }
            for constraint in intent.constraints
        ],
    }

def research_discovery_sources(*, actor, text: str) -> dict:
    """Find bounded external leads tied to a Discovery query, not Makolo facts."""
    import ipaddress
    from urllib.parse import urlsplit

    from django.utils import timezone

    from research_missions import (
        ResearchFamily, ResearchMission, ResearchOrigin, ResearchOriginKind,
    )
    from web_research import WebResearchMode, WebResearchRequest
    from web_research.intelligence_engine import IntelligenceWebResearchEngine

    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Authentification requise.")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 120:
        raise ValueError("Recherche invalide.")
    text = text.strip()
    profile = UserProfile.objects.filter(user=actor).first()
    registry = build_runtime_registry(
        capability=IntelligenceCapability.WEB_RESEARCH,
        profile=profile,
    )
    if not registry.providers_for(IntelligenceCapability.WEB_RESEARCH):
        _record_external_action(
            action="research", status="unavailable",
            reason="connection_unavailable",
        )
        return {"status": "unavailable", "reason": "connection_unavailable",
                "sources": [], "candidates": []}

    mission = ResearchMission(
        primary_family=ResearchFamily.POSSIBILITY,
        subject=text,
        questions=(f"Quelles sources publiques correspondent à : {text} ?",),
        origins=(ResearchOrigin(
            kind=ResearchOriginKind.INITIAL,
            source_ref="discovery:explicit-source-research",
        ),),
        reasons=("Explorer des pistes externes liées à une recherche Makolo.",),
        limits={"max_candidates": 3, "max_queries": 1},
    )
    try:
        result = IntelligenceWebResearchEngine(
            IntelligenceGateway(registry=registry),
        ).execute(WebResearchRequest(
            mission=mission, mode=WebResearchMode.DISCOVER,
            requested_at=timezone.now(),
        ))
    except Exception:
        _record_external_action(
            action="research", status="unavailable",
            reason="provider_unavailable",
        )
        return {"status": "unavailable", "reason": "provider_unavailable",
                "sources": [], "candidates": []}

    if result.outcome.value == "failed":
        reason = _public_failure(result.failure_code or "")
        _record_external_action(
            action="research", status="unavailable", reason=reason,
        )
        return {"status": "unavailable",
                "reason": reason, "sources": [], "candidates": []}

    sources = {}
    for source in result.sources:
        parts = urlsplit(source.locator)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            continue
        hostname = parts.hostname.lower().rstrip(".")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            continue
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            if not ip.is_global:
                continue
        sources[source.source_ref] = {
            "title": (source.title or parts.hostname)[:160],
            "url": source.locator,
            "host": parts.hostname,
        }

    candidates = []
    for candidate in result.candidates:
        citations = [
            sources[ref] for ref in candidate.source_refs if ref in sources
        ][:2]
        if not citations:
            continue
        candidates.append({
            "label": candidate.label[:160],
            "summary": (candidate.summary or "")[:400],
            "sources": citations,
        })
        if len(candidates) >= 3:
            break

    cited_urls = {
        source["url"]
        for candidate in candidates for source in candidate["sources"]
    }
    _record_external_action(
        action="research",
        status="completed" if candidates else "no_results",
        candidates=len(candidates),
    )
    return {
        "status": "completed" if candidates else "no_results",
        "reason": "",
        "sources": [
            source for source in sources.values()
            if source["url"] in cited_urls
        ][:6],
        "candidates": candidates,
    }
