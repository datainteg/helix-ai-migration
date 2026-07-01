"""EventBus port + a synchronous in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from migration_engine.events.events import WILDCARD, DomainEvent

Handler = Callable[[DomainEvent], None]


class EventBus(ABC):
    """Publish/subscribe port. Adapters: in-memory, Redis Streams, Kafka, ..."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None: ...

    @abstractmethod
    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Subscribe to a specific event name, or ``"*"`` for all events."""


@dataclass(frozen=True)
class HandlerError:
    """Captured failure from a subscriber (one bad handler must not break others)."""

    event_name: str
    handler: str
    error: Exception


class InMemoryEventBus(EventBus):
    """Synchronous, ordered, in-process bus for dev/test and single-node runs.

    - Handlers fire in subscription order; wildcard handlers fire after
      name-specific ones.
    - A failing handler is isolated: its exception is captured in ``errors`` and
      dispatch continues (unless ``raise_on_handler_error=True``).
    - ``published`` records every event for assertions/audit.
    """

    def __init__(self, *, raise_on_handler_error: bool = False) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._raise = raise_on_handler_error
        self.published: list[DomainEvent] = []
        self.errors: list[HandlerError] = []

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)
        for handler in self._handlers.get(event.name, []) + self._handlers.get(WILDCARD, []):
            try:
                handler(event)
            except Exception as exc:  # isolate subscriber failures
                self.errors.append(HandlerError(event.name, getattr(handler, "__name__", repr(handler)), exc))
                if self._raise:
                    raise

    def published_names(self) -> list[str]:
        """Convenience for assertions: the ordered list of published event names."""
        return [e.name for e in self.published]
