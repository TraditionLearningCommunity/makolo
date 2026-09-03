from __future__ import annotations

import logging


logger = logging.getLogger("makolo.discovery")
_ALLOWED_CORRECTIONS = {"vertical", "place", "when", "period", "price", "nearby"}


def record_search(
    *,
    result_count: int,
    constraint_count: int,
    vertical: str = "",
    nearby_active: bool = False,
    had_query: bool = False,
    correction_key: str = "",
    error_count: int = 0,
) -> None:
    """Record aggregate Discover behavior without persisting the user's query text."""

    correction = correction_key if correction_key in _ALLOWED_CORRECTIONS else ""
    logger.info(
        "discovery.search",
        extra={
            "makolo_event": "discovery.search",
            "result_count": max(0, int(result_count)),
            "zero_results": int(result_count) == 0,
            "constraint_count": max(0, int(constraint_count)),
            "vertical": vertical[:24],
            "nearby_active": bool(nearby_active),
            "had_query": bool(had_query),
            "correction_key": correction,
            "error_count": max(0, int(error_count)),
        },
    )
