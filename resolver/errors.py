class ResolverError(Exception):
    """Base Actor 4 Resolver error."""


class ResolverContractError(ResolverError):
    """Raised when a Resolver contract is malformed or inconsistent."""


class ResolverLookupError(ResolverError):
    """Raised when a canonical backend lookup cannot be completed safely."""
