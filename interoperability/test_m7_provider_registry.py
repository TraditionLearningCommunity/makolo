from django.test import SimpleTestCase

from .registry import (
    AdapterNotRegistered,
    CapabilityDefinition,
    CapabilityNotSupported,
    InteroperabilityRegistry,
    ProviderDefinition,
    UnknownCapability,
    UnknownProvider,
)


class _DeterministicAdapter:
    pass


class InteroperabilityRegistryTests(SimpleTestCase):
    def setUp(self):
        self.registry = InteroperabilityRegistry()
        self.registry.register_capability(
            CapabilityDefinition(code="example.external.execute", owner="example")
        )
        self.registry.register_capability(
            CapabilityDefinition(code="example.external.read", owner="example")
        )
        self.registry.register_provider(
            ProviderDefinition(
                code="test-provider",
                capabilities={"example.external.execute"},
            )
        )

    def test_unknown_capability_is_rejected(self):
        with self.assertRaises(UnknownCapability):
            self.registry.get_capability("missing.capability")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(UnknownProvider):
            self.registry.get_provider("missing-provider")

    def test_provider_must_only_reference_registered_capabilities(self):
        with self.assertRaises(UnknownCapability):
            self.registry.register_provider(
                ProviderDefinition(code="invalid-provider", capabilities={"missing.capability"})
            )

    def test_provider_that_does_not_support_capability_is_rejected(self):
        with self.assertRaises(CapabilityNotSupported):
            self.registry.resolve_adapter(
                provider="test-provider",
                capability="example.external.read",
            )

    def test_registered_adapter_is_resolved_for_exact_provider_capability_pair(self):
        adapter = _DeterministicAdapter()
        self.registry.register_adapter(
            provider="test-provider",
            capability="example.external.execute",
            adapter=adapter,
        )

        self.assertIs(
            self.registry.resolve_adapter(
                provider="test-provider",
                capability="example.external.execute",
            ),
            adapter,
        )

    def test_missing_adapter_is_explicit(self):
        with self.assertRaises(AdapterNotRegistered):
            self.registry.resolve_adapter(
                provider="test-provider",
                capability="example.external.execute",
            )

    def test_registry_inspection_contains_no_connection_or_secret_material(self):
        capability = self.registry.get_capability("example.external.execute")
        provider = self.registry.get_provider("test-provider")

        self.assertEqual(capability.owner, "example")
        self.assertEqual(provider.capabilities, frozenset({"example.external.execute"}))
        self.assertFalse(hasattr(provider, "secret"))
        self.assertFalse(hasattr(provider, "connection"))
