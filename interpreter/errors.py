class InterpreterError(Exception):
    """Base Interpreter error."""


class InterpreterContractError(InterpreterError):
    """Raised when an Interpreter contract is malformed or inconsistent."""


class UnsupportedMediaError(InterpreterError):
    """Raised when no deterministic strategy supports the supplied media."""


class MalformedContentError(InterpreterError):
    """Raised when bytes claim a supported media type but cannot be parsed safely."""


class ResourceLimitError(InterpreterError):
    """Raised when bounded interpretation limits are exceeded."""
