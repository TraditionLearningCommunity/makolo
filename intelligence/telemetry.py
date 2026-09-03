from __future__ import annotations

import logging


logger = logging.getLogger("makolo.intelligence")


def record_invocation(
    *,
    capability: str,
    available: bool,
    provider_key: str = "",
    model: str = "",
    reason: str = "",
    latency_ms: int = 0,
    feature: str = "",
) -> None:
    """Emit privacy-safe operational metadata for one Intelligence attempt.

    Raw prompts, provider inputs and provider outputs are deliberately excluded.
    """

    logger.info(
        "intelligence.invocation",
        extra={
            "makolo_event": "intelligence.invocation",
            "capability": capability,
            "available": bool(available),
            "provider_key": provider_key,
            "model": model,
            "reason": reason,
            "latency_ms": max(0, int(latency_ms)),
            "feature": feature[:80],
        },
    )
