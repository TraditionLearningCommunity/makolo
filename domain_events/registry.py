from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class DomainEventConsumer:
    name: str
    handler: Callable
    event_types: frozenset[str] | None = None


_consumers: dict[str, DomainEventConsumer] = {}


def register_consumer(name: str, handler: Callable, *, event_types: Iterable[str] | None = None):
    normalized = (name or "").strip()
    if not normalized:
        raise ValueError("Un consumer Domain Event doit avoir un nom stable.")
    _consumers[normalized] = DomainEventConsumer(
        name=normalized,
        handler=handler,
        event_types=frozenset(event_types) if event_types is not None else None,
    )
    return handler


def unregister_consumer(name: str):
    _consumers.pop(name, None)


def registered_consumers_for(event_type: str):
    return tuple(
        consumer
        for consumer in _consumers.values()
        if consumer.event_types is None or event_type in consumer.event_types
    )
