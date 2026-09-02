import json
import os
from unittest.mock import patch

from django.test import TestCase

from .capabilities import IntelligenceCapability
from .contracts import IntelligenceRequest
from .credentials import get_provider_secret, set_provider_secret
from .gateway import IntelligenceGateway
from .models import IntelligenceRoute, ProviderConnection, ProviderHealth, ProviderProtocol, ProviderScope
from .runtime import build_runtime_registry


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class IntelligenceProviderRegistryTests(TestCase):
    def setUp(self):
        self.connection = ProviderConnection.objects.create(
            name="Test provider",
            protocol=ProviderProtocol.OPENAI_COMPATIBLE,
            base_url="https://provider.example.test/v1",
            default_model="test-model",
            scope=ProviderScope.PLATFORM,
            enabled=True,
            health_status=ProviderHealth.HEALTHY,
        )

    def test_credentials_are_encrypted_and_round_trip(self):
        with patch.dict(os.environ, {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"}):
            credential = set_provider_secret(connection=self.connection, secret="sk-example-secret-1234")
            self.assertNotIn("sk-example-secret-1234", credential.encrypted_secret)
            self.assertNotEqual(credential.key_hint, "sk-example-secret-1234")
            self.assertEqual(get_provider_secret(connection=self.connection), "sk-example-secret-1234")

    def test_runtime_registry_uses_enabled_route_and_credential(self):
        IntelligenceRoute.objects.create(
            capability=IntelligenceCapability.STRUCTURED_GENERATE.value,
            connection=self.connection,
            priority=10,
        )
        with patch.dict(os.environ, {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"}):
            set_provider_secret(connection=self.connection, secret="sk-example-secret-1234")
            registry = build_runtime_registry(capability=IntelligenceCapability.STRUCTURED_GENERATE)
        self.assertEqual(len(registry.providers), 1)
        self.assertEqual(registry.providers[0].model, "test-model")

    def test_openai_compatible_structured_generation_is_validated(self):
        IntelligenceRoute.objects.create(
            capability=IntelligenceCapability.STRUCTURED_GENERATE.value,
            connection=self.connection,
        )
        with patch.dict(os.environ, {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-test-master-key"}):
            set_provider_secret(connection=self.connection, secret="sk-example-secret-1234")
            gateway = IntelligenceGateway(
                build_runtime_registry(capability=IntelligenceCapability.STRUCTURED_GENERATE)
            )
            with patch(
                "urllib.request.urlopen",
                return_value=_FakeResponse(
                    {"choices": [{"message": {"content": '{"vertical":"transport"}'}}]}
                ),
            ):
                result = gateway.execute(
                    IntelligenceRequest(
                        capability=IntelligenceCapability.STRUCTURED_GENERATE,
                        input={"text": "voyager demain"},
                    )
                )
        self.assertTrue(result.available)
        self.assertEqual(result.output, {"vertical": "transport"})
        self.assertEqual(result.model, "test-model")

    def test_missing_master_key_keeps_runtime_route_unavailable(self):
        IntelligenceRoute.objects.create(
            capability=IntelligenceCapability.TEXT_GENERATE.value,
            connection=self.connection,
        )
        with patch.dict(os.environ, {}, clear=True):
            registry = build_runtime_registry(capability=IntelligenceCapability.TEXT_GENERATE)
        self.assertEqual(registry.providers, [])
