"""Controlled interoperability boundaries for Makolo.

M7 keeps provider availability separate from authorization. Importing this
package never implies that a Profile or Space has authorized a Connection.
"""

from .registry import (
    AdapterNotRegistered,
    CapabilityDefinition,
    CapabilityNotSupported,
    InteroperabilityRegistry,
    ProviderDefinition,
    UnknownCapability,
    UnknownProvider,
)

__all__ = [
    "AdapterNotRegistered",
    "CapabilityDefinition",
    "CapabilityNotSupported",
    "InteroperabilityRegistry",
    "ProviderDefinition",
    "UnknownCapability",
    "UnknownProvider",
]
