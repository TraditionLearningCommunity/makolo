from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class RegistryError(LookupError):
    """Base error for provider availability/registration failures."""


class UnknownCapability(RegistryError):
    pass


class UnknownProvider(RegistryError):
    pass


class CapabilityNotSupported(RegistryError):
    pass


class AdapterNotRegistered(RegistryError):
    pass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    """A provider-neutral external capability Makolo may request.

    ``owner`` names the Makolo domain that owns the business truth. It is
    descriptive metadata for the registry, not an authorization shortcut.
    """

    code: str
    owner: str

    def __post_init__(self) -> None:
        code = self.code.strip()
        owner = self.owner.strip()
        if not code:
            raise ValueError("Capability code cannot be empty.")
        if not owner:
            raise ValueError("Capability owner cannot be empty.")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "owner", owner)


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    """An installed provider implementation and the capabilities it supports.

    A registered provider is only *available* to Makolo. It is not authorized
    for any Profile or Space until the Connection layer says so.
    """

    code: str
    capabilities: frozenset[str]

    def __init__(self, *, code: str, capabilities: Iterable[str]):
        normalized_code = code.strip()
        normalized_capabilities = frozenset(item.strip() for item in capabilities if item.strip())
        if not normalized_code:
            raise ValueError("Provider code cannot be empty.")
        object.__setattr__(self, "code", normalized_code)
        object.__setattr__(self, "capabilities", normalized_capabilities)


class InteroperabilityRegistry:
    """Provider-neutral registry for installed capabilities and adapters.

    This object deliberately contains no credentials, Connection state,
    Permission/Mandate checks or business transitions. Those remain separate
    Makolo contracts. M7.1 answers only: what capability exists, what installed
    provider supports it, and which adapter implements that pair?
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._providers: dict[str, ProviderDefinition] = {}
        self._adapters: dict[tuple[str, str], Any] = {}

    def register_capability(self, definition: CapabilityDefinition) -> None:
        existing = self._capabilities.get(definition.code)
        if existing is not None and existing != definition:
            raise ValueError(f"Capability {definition.code!r} is already registered differently.")
        self._capabilities[definition.code] = definition

    def register_provider(self, definition: ProviderDefinition) -> None:
        for capability_code in definition.capabilities:
            if capability_code not in self._capabilities:
                raise UnknownCapability(capability_code)
        existing = self._providers.get(definition.code)
        if existing is not None and existing != definition:
            raise ValueError(f"Provider {definition.code!r} is already registered differently.")
        self._providers[definition.code] = definition

    def register_adapter(self, *, provider: str, capability: str, adapter: Any) -> None:
        provider_definition = self.get_provider(provider)
        self.get_capability(capability)
        if capability not in provider_definition.capabilities:
            raise CapabilityNotSupported(f"{provider}:{capability}")
        self._adapters[(provider, capability)] = adapter

    def get_capability(self, code: str) -> CapabilityDefinition:
        try:
            return self._capabilities[code]
        except KeyError as exc:
            raise UnknownCapability(code) from exc

    def get_provider(self, code: str) -> ProviderDefinition:
        try:
            return self._providers[code]
        except KeyError as exc:
            raise UnknownProvider(code) from exc

    def providers_for(self, capability: str) -> tuple[ProviderDefinition, ...]:
        self.get_capability(capability)
        return tuple(
            provider
            for provider in self._providers.values()
            if capability in provider.capabilities
        )

    def resolve_adapter(self, *, provider: str, capability: str) -> Any:
        provider_definition = self.get_provider(provider)
        self.get_capability(capability)
        if capability not in provider_definition.capabilities:
            raise CapabilityNotSupported(f"{provider}:{capability}")
        try:
            return self._adapters[(provider, capability)]
        except KeyError as exc:
            raise AdapterNotRegistered(f"{provider}:{capability}") from exc
