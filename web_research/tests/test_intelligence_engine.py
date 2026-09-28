import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.capabilities import (
    IntelligenceCapability,
    PERSISTED_INTELLIGENCE_ROUTE_CAPABILITIES,
)
from intelligence.contracts import IntelligenceRequest
from intelligence.gateway import IntelligenceGateway
from intelligence.models import IntelligenceRoute
from intelligence.providers.openai_responses_web import (
    OpenAIResponsesWebResearchProvider,
)
from intelligence.registry import IntelligenceRegistry
from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchOrigin,
    ResearchOriginKind,
)
from web_research import (
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchStopReason,
)
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
        origins=(
            ResearchOrigin(
                kind=ResearchOriginKind.INITIAL,
                source_ref="seed:mechanical-engineering-scholarships",
            ),
        ),
        reasons=("Construire la connaissance Makolo",),
        limits={"max_candidates": 25, "max_queries": 5},
    )


def _response_payload(*, source_url="https://example.org/scholarship", candidate_url=None):
    candidate_url = candidate_url or source_url
    structured = {
        "stop_reason": "coverage_saturated",
        "candidates": [
            {
                "label": "Mechanical Engineering Scholarship",
                "type_hints": ["program"],
                "summary": "Master scholarship in mechanical engineering.",
                "source_urls": [candidate_url],
            }
        ],
    }
    return {
        "status": "completed",
        "output": [
            {
                "type": "web_search_call",
                "id": "search-1",
                "action": {
                    "type": "search",
                    "queries": ["mechanical engineering scholarships"],
                    "sources": [
                        {
                            "type": "url",
                            "url": source_url,
                            "title": "Official scholarship page",
                        }
                    ],
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(structured),
                        "annotations": [],
                    }
                ],
            },
        ],
    }


class WebResearchIntelligenceCapabilityTests(SimpleTestCase):
    def test_web_research_is_runtime_capability_but_not_persisted_route_yet(self):
        self.assertIn(
            IntelligenceCapability.WEB_RESEARCH,
            set(IntelligenceCapability),
        )
        self.assertNotIn(
            IntelligenceCapability.WEB_RESEARCH,
            PERSISTED_INTELLIGENCE_ROUTE_CAPABILITIES,
        )
        persisted_choices = {
            value
            for value, _label in IntelligenceRoute._meta.get_field("capability").choices
        }
        self.assertEqual(
            persisted_choices,
            {
                "text_generate",
                "structured_generate",
                "embed",
                "rerank",
            },
        )


class OpenAIResponsesWebResearchProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = OpenAIResponsesWebResearchProvider(
            key="provider-test",
            base_url="https://api.openai.example/v1",
            api_key="test-secret",
            model="test-web-model",
            timeout_seconds=20,
        )
        self.request = IntelligenceRequest(
            capability=IntelligenceCapability.WEB_RESEARCH,
            input={
                "request": WebResearchRequest(
                    mission=_mission(),
                    mode=WebResearchMode.DISCOVER,
                    requested_at=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
                ).to_payload()
            },
            metadata={"feature": "web_research"},
        )

    def test_adapter_uses_responses_web_search_without_implicit_location(self):
        captured = {}

        def fake_open(request, *, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse(_response_payload())

        with patch(
            "intelligence.providers.openai_responses_web._open_url",
            side_effect=fake_open,
        ):
            result = self.provider.execute(self.request)

        self.assertTrue(result.available)
        self.assertEqual(result.provider_key, "provider-test")
        self.assertEqual(result.model, "test-web-model")
        self.assertEqual(captured["url"], "https://api.openai.example/v1/responses")
        self.assertFalse(captured["payload"]["store"])
        self.assertEqual(captured["payload"]["tool_choice"], "required")
        self.assertEqual(captured["payload"]["tools"], [{"type": "web_search"}])
        self.assertEqual(
            captured["payload"]["include"],
            ["web_search_call.action.sources"],
        )
        self.assertEqual(captured["payload"]["max_tool_calls"], 5)
        serialized = json.dumps(captured["payload"], sort_keys=True)
        self.assertNotIn('"location"', serialized)
        self.assertNotIn("Lubumbashi", serialized)
        self.assertNotIn("Kinshasa", serialized)
        self.assertEqual(
            result.output["sources"][0]["url"],
            "https://example.org/scholarship",
        )

    def test_adapter_normalizes_incomplete_response_to_provider_limit(self):
        payload = _response_payload()
        payload["status"] = "incomplete"
        with patch(
            "intelligence.providers.openai_responses_web._open_url",
            return_value=_FakeResponse(payload),
        ):
            result = self.provider.execute(self.request)
        self.assertEqual(result.output["stop_reason"], "provider_limit")

    def test_adapter_does_not_log_or_return_api_key(self):
        with patch(
            "intelligence.providers.openai_responses_web._open_url",
            return_value=_FakeResponse(_response_payload()),
        ):
            result = self.provider.execute(self.request)
        self.assertNotIn("test-secret", repr(result))


class IntelligenceWebResearchEngineTests(SimpleTestCase):
    def _engine(self, payload):
        provider = OpenAIResponsesWebResearchProvider(
            key="provider-test",
            base_url="https://api.openai.example/v1",
            api_key="test-secret",
            model="test-web-model",
        )
        gateway = IntelligenceGateway(
            IntelligenceRegistry(providers=[provider])
        )
        start = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        clock = _Clock(start, start + timedelta(seconds=2))
        return IntelligenceWebResearchEngine(gateway, clock=clock), provider

    def _request(self):
        return WebResearchRequest(
            mission=_mission(),
            mode=WebResearchMode.DISCOVER,
            requested_at=datetime(2026, 9, 28, 11, 59, tzinfo=timezone.utc),
        )

    def test_engine_translates_gateway_output_to_sourced_makolo_result(self):
        engine, _provider = self._engine(_response_payload())
        with patch(
            "intelligence.providers.openai_responses_web._open_url",
            return_value=_FakeResponse(_response_payload()),
        ):
            result = engine.execute(self._request())

        self.assertEqual(result.outcome, WebResearchOutcome.COMPLETED)
        self.assertEqual(
            result.stop_reason,
            WebResearchStopReason.COVERAGE_SATURATED,
        )
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(
            result.candidates[0].source_refs,
            (result.sources[0].source_ref,),
        )
        self.assertEqual(
            result.engine_metadata["provider_key"],
            "provider-test",
        )
        self.assertEqual(
            result.engine_metadata["model"],
            "test-web-model",
        )

    def test_engine_rejects_candidate_not_backed_by_provider_sources(self):
        engine, _provider = self._engine(_response_payload())
        payload = _response_payload(
            candidate_url="https://invented.example/not-consulted"
        )
        with patch(
            "intelligence.providers.openai_responses_web._open_url",
            return_value=_FakeResponse(payload),
        ):
            result = engine.execute(self._request())

        self.assertEqual(result.outcome, WebResearchOutcome.NO_RESULTS)
        self.assertEqual(result.candidates, ())
        self.assertIn("candidate_unknown_source", result.warning_codes)

    def test_gateway_unavailability_becomes_failed_web_research_result(self):
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[]))
        start = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        engine = IntelligenceWebResearchEngine(
            gateway,
            clock=_Clock(start, start + timedelta(seconds=1)),
        )
        result = engine.execute(self._request())
        self.assertEqual(result.outcome, WebResearchOutcome.FAILED)
        self.assertEqual(result.stop_reason, WebResearchStopReason.FAILED)
        self.assertEqual(result.failure_code, "capability_not_configured")
