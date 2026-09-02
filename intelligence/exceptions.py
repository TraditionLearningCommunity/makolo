class IntelligenceError(RuntimeError):
    """Base error for provider-neutral intelligence infrastructure."""


class ProviderUnavailable(IntelligenceError):
    pass


class CapabilityUnsupported(IntelligenceError):
    pass


class InvalidProviderResult(IntelligenceError):
    pass
