import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest
from intelligence.exceptions import ProviderUnavailable
from intelligence.gateway import IntelligenceGateway
from intelligence.providers.exa_web import ExaWebResearchProvider
from intelligence.providers.tavily_web import TavilyWebResearchProvider
from intelligence.registry import IntelligenceRegistry
from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import WebResearchMode, WebResearchRequest
from web_research.intelligence_engine import IntelligenceWebResearchEngine


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _Clock:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0)


def _mission():
    return ResearchMission(
        primary_family=ResearchFamily.POSSIBILITY,
        subject="Bourses de Master en génie mécanique",
        questions=("Quelles possibilités existent ?",),
        unknowns=("Quelles sont les conditions ?",),
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.INITIAL,
                source_ref="seed:web-research-provider-pack",
            ),
        ),
        reasons=("Construire la connaissance Makolo",),
        limits={"max_candidates": 3, "max_queries": 2},
    )


def _web_request():
    return WebResearchRequest(
        mission=_mission(),
        mode=WebResearchMode.DISCOVER,
        requested_at=datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc),
    )


def _intelligence_request():
    return IntelligenceRequest(
        capability=IntelligenceCapability.WEB_RESEARCH,
        input={"request": _web_request().to_payload()},
        metadata={"feature": "web_research"},
    )


class TavilyWebResearchProviderTests(SimpleTestCase):
    def test_tavily_returns_only_sourced_candidates_and_respects_limit(self):
        provider = TavilyWebResearchProvider(
            key="tavily-test",
            base_url="https://api.tavily.example",
            api_key="tvly-test-secret",
            timeout_seconds=12,
        )
        captured = {}

        def fake_open(request, *, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "results": [
                        {
                            "title": "Official scholarship page",
                            "url": "https://example.org/scholarship",
                            "content": "Funded mechanical engineering Master scholarship.",
                        }
                    ]
                }
            )

        with patch(
            "intelligence.providers.tavily_web._open_url",
            side_effect=fake_open,
        ):
            result = provider.execute(_intelligence_request())

        self.assertTrue(result.available)
        self.assertEqual(captured["url"], "https://api.tavily.example/search")
        self.assertEqual(captured["payload"]["max_results"], 3)
        self.assertEqual(captured["payload"]["search_depth"], "basic")
        self.assertFalse(captured["payload"]["include_answer"])
        self.assertNotIn("country", captured["payload"])
        self.assertEqual(
            result.output["candidates"][0]["source_urls"],
            ["https://example.org/scholarship"],
        )
        self.assertNotIn("tvly-test-secret", repr(result))

    def test_tavily_invalid_result_is_controlled(self):
        provider = TavilyWebResearchProvider(
            key="tavily-test",
            base_url="https://api.tavily.example",
            api_key="secret",
        )
        with patch(
            "intelligence.providers.tavily_web._open_url",
            return_value=_FakeResponse({"results": "not-a-list"}),
        ):
            with self.assertRaisesMessage(Exception, "tavily_results_invalid"):
                provider.execute(_intelligence_request())


class ExaWebResearchProviderTests(SimpleTestCase):
    def test_exa_returns_only_sourced_candidates_and_no_implicit_location(self):
        provider = ExaWebResearchProvider(
            key="exa-test",
            base_url="https://api.exa.example",
            api_key="exa-test-secret",
            timeout_seconds=12,
        )
        captured = {}

        def fake_open(request, *, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = {
                key.casefold(): value for key, value in request.header_items()
            }
            return _FakeResponse(
                {
                    "results": [
                        {
                            "title": "Scholarship reference",
                            "url": "https://example.edu/funding",
                            "highlights": [
                                "Applications are open for mechanical engineering."
                            ],
                        }
                    ]
                }
            )

        with patch(
            "intelligence.providers.exa_web._open_url",
            side_effect=fake_open,
        ):
            result = provider.execute(_intelligence_request())

        self.assertTrue(result.available)
        self.assertEqual(captured["url"], "https://api.exa.example/search")
        self.assertEqual(captured["payload"]["numResults"], 3)
        self.assertEqual(captured["payload"]["type"], "auto")
        self.assertNotIn("userLocation", captured["payload"])
        self.assertEqual(captured["headers"]["x-api-key"], "exa-test-secret")
        self.assertEqual(
            result.output["candidates"][0]["summary"],
            "Applications are open for mechanical engineering.",
        )
        self.assertNotIn("exa-test-secret", repr(result))


class ProviderNeutralWebResearchRoutingTests(SimpleTestCase):
    def test_gateway_falls_back_from_tavily_to_exa_and_engine_keeps_contract(self):
        tavily = TavilyWebResearchProvider(
            key="tavily",
            base_url="https://api.tavily.example",
            api_key="secret-t",
        )
        exa = ExaWebResearchProvider(
            key="exa",
            base_url="https://api.exa.example",
            api_key="secret-e",
        )
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[tavily, exa]))
        start = datetime(2026, 10, 3, 18, 1, tzinfo=timezone.utc)
        engine = IntelligenceWebResearchEngine(
            gateway,
            clock=_Clock(start, start + timedelta(seconds=1)),
        )

        with (
            patch(
                "intelligence.providers.tavily_web._open_url",
                side_effect=ProviderUnavailable("offline"),
            ),
            patch(
                "intelligence.providers.exa_web._open_url",
                return_value=_FakeResponse(
                    {
                        "results": [
                            {
                                "title": "Official funding page",
                                "url": "https://example.edu/funding",
                                "highlights": ["Master funding opportunity."],
                            }
                        ]
                    }
                ),
            ),
        ):
            result = engine.execute(_web_request())

        self.assertEqual(result.engine_metadata["provider_key"], "exa")
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(
            result.candidates[0].source_refs,
            (result.sources[0].source_ref,),
        )
