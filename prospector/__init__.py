"""Makolo Prospecteur core contracts.

This package is deliberately framework-independent. Django, PostgreSQL,
Crawlee and provider integrations belong behind adapters/ports.
"""

from .contracts import (
    CONTRACT_VERSION,
    ProspectingCandidate,
    ProspectingEvidence,
    ProspectingTarget,
)
from .errors import ProspectorContractError

__all__ = [
    "CONTRACT_VERSION",
    "ProspectingCandidate",
    "ProspectingEvidence",
    "ProspectingTarget",
    "ProspectorContractError",
]
