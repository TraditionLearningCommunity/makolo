class ProspectorContractError(ValueError):
    """Raised when a Prospector contract value violates a core invariant."""


class UnsupportedTargetKindError(ProspectorContractError):
    """Raised when no canonicalization contract exists for a target kind."""


class FrontierConflictError(ProspectorContractError):
    """Raised when durable state conflicts with a canonical target identity."""


class FrontierClaimError(ProspectorContractError):
    """Raised when a worker attempts an invalid or stale Frontier transition."""
