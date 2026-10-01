"""Explicit errors for framework-independent Mayele contracts."""


class MayeleContractError(ValueError):
    """Raised when a Mayele semantic contract is invalid."""


class KnowledgeGateError(MayeleContractError):
    """Raised when knowledge fails the MY1 admission gate."""
