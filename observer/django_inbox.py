from __future__ import annotations

from dataclasses import dataclass

from asgiref.sync import sync_to_async

from .adapters.crawlee_inbox import observation_target_from_crawlee_request
from .django_store import absorb_observation_target


@dataclass(frozen=True, slots=True)
class InboxDrainStats:
    fetched: int = 0
    absorbed: int = 0
    replayed: int = 0


async def drain_crawlee_inbox(
    request_queue,
    *,
    limit: int = 100,
) -> InboxDrainStats:
    """Move durable ownership from Crawlee into Observer storage.

    Database commit happens before the queue item is acknowledged. A crash after
    commit but before mark_request_as_handled is therefore an idempotent replay.
    """

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    fetched = absorbed = replayed = 0
    for _index in range(limit):
        request = await request_queue.fetch_next_request()
        if request is None:
            break
        fetched += 1
        try:
            target = observation_target_from_crawlee_request(request)
            _handoff, created = await sync_to_async(
                absorb_observation_target,
                thread_sensitive=True,
            )(target)
        except Exception:
            await request_queue.reclaim_request(
                request,
                forefront=False,
            )
            raise
        await request_queue.mark_request_as_handled(request)
        if created:
            absorbed += 1
        else:
            replayed += 1
    return InboxDrainStats(
        fetched=fetched,
        absorbed=absorbed,
        replayed=replayed,
    )
