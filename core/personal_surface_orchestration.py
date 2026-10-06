from __future__ import annotations

from typing import TypeVar


T = TypeVar("T")


def pass_now_candidates_through_molongo(candidates: T) -> T:
    """Current Now Me seam toward Molongo.

    Molongo has not defined its future input contract yet. Until it does, the
    server passes the already-collected candidate data through unchanged.
    """

    return candidates


def pass_ongoing_candidates_through_molongo(candidates: T) -> T:
    """Current En cours Me seam toward Molongo.

    This deliberately preserves the existing server read model unchanged and
    does not define future Molongo selection, ranking or enrichment.
    """

    return candidates


def pass_discovery_candidates_through_molongo(candidates: T) -> T:
    """Current Discover Me seam toward Molongo.

    Discovery candidates are already collected by the canonical server
    composition. Molongo is a no-op here until its real needs are specified.
    """

    return candidates
