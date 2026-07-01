"""Event-driven backbone (port + in-memory implementation).

Domain events are how bounded contexts integrate without coupling: the engine
publishes facts ("a run completed", "recon finished"); consumers (catalog sync,
knowledge graph, observability, webhooks, velocity analytics, billing meters)
react. Temporal orchestrates *work*; the event bus distributes *facts*.

``EventBus`` is a port. ``InMemoryEventBus`` is the dev/test implementation; a
Redis Streams / NATS / Kafka adapter can implement the same interface later
without touching publishers or subscribers.
"""

from __future__ import annotations

from migration_engine.events.events import DomainEvent, EventName
from migration_engine.events.bus import EventBus, InMemoryEventBus

__all__ = ["DomainEvent", "EventName", "EventBus", "InMemoryEventBus"]
