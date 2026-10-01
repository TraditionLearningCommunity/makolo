from enum import Enum


class KnowledgeValue(str, Enum):
    """Explicit epistemic/non-value states.

    These values are intentionally distinct from Python None and boolean False.
    """

    UNKNOWN = "UNKNOWN"
    FALSE = "FALSE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CLOSED = "CLOSED"
