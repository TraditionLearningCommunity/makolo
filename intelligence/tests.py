from django.test import SimpleTestCase

from .capabilities import IntelligenceCapability
from .contracts import IntelligenceRequest, IntelligenceResult
from .exceptions import ProviderUnavailable
from .gateway import IntelligenceGateway
from .providers.base import IntelligenceProvider
from .providers.noop import NoOpIntelligenceProvider
from .registry import IntelligenceRegistry


class EchoProvider(IntelligenceProvider):
    key = "echo"
    capabilities = frozenset({IntelligenceCapability.STRUCTURED_GENERATE})

    def execute(self, request):
        return IntelligenceResult(
            available=True,
            output={"echo": request.input},
            provider_key=self.key,
            model="test",
        )


class FailingProvider(EchoProvider):
    key = "failing"

    def execute(self, request):
        raise ProviderUnavailable("offline")


class IntelligenceFoundationTests(SimpleTestCase):
    def test_noop_provider_is_safe_when_nothing_is_configured(self):
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[NoOpIntelligenceProvider()]))
        result = gateway.execute(
            IntelligenceRequest(
                capability=IntelligenceCapability.STRUCTURED_GENERATE,
                input={"text": "bonjour"},
            )
        )
        self.assertFalse(result.available)

    def test_gateway_routes_only_to_provider_supporting_capability(self):
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[EchoProvider()]))
        result = gateway.execute(
            IntelligenceRequest(
                capability=IntelligenceCapability.STRUCTURED_GENERATE,
                input={"text": "bonjour"},
            )
        )
        self.assertTrue(result.available)
        self.assertEqual(result.provider_key, "echo")
        self.assertEqual(result.output["echo"]["text"], "bonjour")

    def test_gateway_falls_through_provider_failure(self):
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[FailingProvider(), EchoProvider()]))
        result = gateway.execute(
            IntelligenceRequest(
                capability=IntelligenceCapability.STRUCTURED_GENERATE,
                input={"text": "bonjour"},
            )
        )
        self.assertTrue(result.available)
        self.assertEqual(result.provider_key, "echo")

    def test_missing_capability_is_controlled_unavailability(self):
        gateway = IntelligenceGateway(IntelligenceRegistry(providers=[EchoProvider()]))
        result = gateway.execute(
            IntelligenceRequest(
                capability=IntelligenceCapability.EMBED,
                input={"texts": ["bonjour"]},
            )
        )
        self.assertFalse(result.available)
        self.assertEqual(result.reason, "capability_not_configured")
