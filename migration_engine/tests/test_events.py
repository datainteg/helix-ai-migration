"""Tests for the event bus port + in-memory implementation."""

from __future__ import annotations

import pytest

from migration_engine.events.bus import InMemoryEventBus
from migration_engine.events.events import DomainEvent, EventName


def test_specific_subscription_receives_only_its_event():
    bus = InMemoryEventBus()
    got: list[DomainEvent] = []
    bus.subscribe(EventName.RUN_COMPLETED.value, got.append)

    bus.publish(DomainEvent.of(EventName.RUN_STARTED, payload={"run": 1}))
    bus.publish(DomainEvent.of(EventName.RUN_COMPLETED, payload={"run": 1}))

    assert [e.name for e in got] == [EventName.RUN_COMPLETED.value]


def test_wildcard_receives_everything_after_specific():
    bus = InMemoryEventBus()
    order: list[str] = []
    bus.subscribe(EventName.RUN_COMPLETED.value, lambda e: order.append("specific"))
    bus.subscribe("*", lambda e: order.append("wildcard"))

    bus.publish(DomainEvent.of(EventName.RUN_COMPLETED))
    assert order == ["specific", "wildcard"]


def test_published_log_records_all_events():
    bus = InMemoryEventBus()
    bus.publish(DomainEvent.of(EventName.MIGRATION_UNIT_CREATED))
    bus.publish(DomainEvent.of(EventName.ASSESSMENT_COMPLETED))
    assert bus.published_names() == [
        EventName.MIGRATION_UNIT_CREATED.value,
        EventName.ASSESSMENT_COMPLETED.value,
    ]


def test_handler_error_is_isolated_by_default():
    bus = InMemoryEventBus()
    fired: list[str] = []

    def boom(_e: DomainEvent) -> None:
        raise RuntimeError("subscriber failed")

    bus.subscribe(EventName.RECON_COMPLETED.value, boom)
    bus.subscribe(EventName.RECON_COMPLETED.value, lambda e: fired.append("ok"))

    bus.publish(DomainEvent.of(EventName.RECON_COMPLETED))  # does not raise

    assert fired == ["ok"]                       # good handler still ran
    assert len(bus.errors) == 1
    assert bus.errors[0].handler == "boom"


def test_handler_error_can_propagate_when_strict():
    bus = InMemoryEventBus(raise_on_handler_error=True)

    def boom(_e: DomainEvent) -> None:
        raise ValueError("strict")

    bus.subscribe("*", boom)
    with pytest.raises(ValueError):
        bus.publish(DomainEvent.of(EventName.RUN_FAILED))


def test_event_of_accepts_enum_or_str():
    assert DomainEvent.of(EventName.JIRA_SYNCED).name == "integration.jira.synced"
    assert DomainEvent.of("custom.plugin.event").name == "custom.plugin.event"
