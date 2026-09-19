class ObserverError(Exception):
    """Base error for the Observer bounded context."""


class ObserverContractError(ObserverError, ValueError):
    """Raised when an Observer contract is internally inconsistent."""


class ObserverStateConflictError(ObserverError):
    """Raised when durable Observer state conflicts with an idempotent replay."""


class ArtifactStorageError(ObserverError):
    """Raised when an artifact cannot be stored or read safely."""
