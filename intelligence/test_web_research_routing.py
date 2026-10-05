import json
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from intelligence.capabilities import IntelligenceCapability
from intelligence.credentials import set_provider_secret
from intelligence.health import test_provider_connection
from intelligence.models import (
    IntelligenceRoute,
    ProviderConnection,
    ProviderHealth,
    ProviderProtocol,
    ProviderScope,
)
from intelligence.providers.exa_web import ExaWebResearchProvider
from intelligence.providers.openai_responses_web import (
    OpenAIResponsesWebResearchProvider,
)
from intelligence.providers.tavily_web import TavilyWebResearchProvider
from intelligence.runtime import build_runtime_registry


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class WebResearchRuntimeRoutingTests(TestCase):
    def _connection(
        self,
        *,
        name,
        protocol,
        base_url,
        default_model="",
        priority=100,
    ):
        return ProviderConnection.objects.create(
            name=name,
            protocol=protocol,
            base_url=base_url,
            default_model=default_model,
            scope=ProviderScope.PLATFORM,
            enabled=True,
            priority=priority,
            health_status=ProviderHealth.HEALTHY,
        )

    def test_tavily_and_exa_do_not_require_fake_model_names(self):
        for protocol in (
            ProviderProtocol.TAVILY_SEARCH,
            ProviderProtocol.EXA_SEARCH,
        ):
            with self.subTest(protocol=protocol):
                connection = ProviderConnection(
                    name="Search provider",
                    protocol=protocol,
                    base_url="https://provider.example",
                    default_model="",
                    scope=ProviderScope.PLATFORM,
                )
                connection.full_clean()

    def test_openai_web_requires_model(self):
        connection = ProviderConnection(
            name="OpenAI Web",
            protocol=ProviderProtocol.OPENAI_RESPONSES_WEB,
            base_url="https://api.openai.example/v1",
            default_model="",
            scope=ProviderScope.PLATFORM,
        )
        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_registry_builds_web_research_providers_in_route_order(self):
        tavily = self._connection(
            name="Tavily",
            protocol=ProviderProtocol.TAVILY_SEARCH,
            base_url="https://api.tavily.example",
            priority=30,
        )
        openai = self._connection(
            name="OpenAI Web",
            protocol=ProviderProtocol.OPENAI_RESPONSES_WEB,
            base_url="https://api.openai.example/v1",
            default_model="web-model",
            priority=20,
        )
        exa = self._connection(
            name="Exa",
            protocol=ProviderProtocol.EXA_SEARCH,
            base_url="https://api.exa.example",
            priority=10,
        )
        for priority, connection in enumerate((tavily, openai, exa), start=1):
            IntelligenceRoute.objects.create(
                capability=IntelligenceCapability.WEB_RESEARCH.value,
                connection=connection,
                priority=priority,
            )

        with patch.dict(
            os.environ,
            {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"},
        ):
            for connection in (tavily, openai, exa):
                set_provider_secret(
                    connection=connection,
                    secret=f"secret-{connection.name}",
                )
            registry = build_runtime_registry(
                capability=IntelligenceCapability.WEB_RESEARCH
            )

        self.assertEqual(
            [type(provider) for provider in registry.providers],
            [
                TavilyWebResearchProvider,
                OpenAIResponsesWebResearchProvider,
                ExaWebResearchProvider,
            ],
        )


    def test_explicit_health_check_uses_configured_tavily_provider(self):
        tavily = self._connection(
            name="Tavily",
            protocol=ProviderProtocol.TAVILY_SEARCH,
            base_url="https://api.tavily.example",
        )
        with patch.dict(
            os.environ,
            {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"},
        ):
            set_provider_secret(connection=tavily, secret="secret-tavily")
            with patch(
                "intelligence.providers.tavily_web._open_url",
                return_value=_FakeResponse(
                    {
                        "results": [
                            {
                                "title": "Makolo",
                                "url": "https://example.org/makolo",
                                "content": "Public source.",
                            }
                        ]
                    }
                ),
            ):
                status = test_provider_connection(tavily)

        tavily.refresh_from_db()
        self.assertEqual(status, ProviderHealth.HEALTHY)
        self.assertEqual(tavily.health_status, ProviderHealth.HEALTHY)
        self.assertIsNotNone(tavily.last_checked_at)

    def test_search_only_protocol_never_routes_generation(self):
        tavily = self._connection(
            name="Tavily",
            protocol=ProviderProtocol.TAVILY_SEARCH,
            base_url="https://api.tavily.example",
        )
        IntelligenceRoute.objects.create(
            capability=IntelligenceCapability.WEB_RESEARCH.value,
            connection=tavily,
        )
        with patch.dict(
            os.environ,
            {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"},
        ):
            set_provider_secret(connection=tavily, secret="secret-tavily")
            registry = build_runtime_registry(
                capability=IntelligenceCapability.TEXT_GENERATE
            )
        self.assertEqual(registry.providers, [])
