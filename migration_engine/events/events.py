"""Domain event definitions.

Events are immutable facts. Infrastructure (the publisher adapter) stamps
``occurred_at`` / ids when crossing the process boundary; the core keeps events
pure so they are deterministic and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventName(str, Enum):
    """Canonical domain event names (dot-namespaced by context)."""

    # migration lifecycle
    MIGRATION_UNIT_CREATED = "migration.unit.created"
    RUN_STARTED = "migration.run.started"
    RUN_PROGRESSED = "migration.run.progressed"
    RUN_COMPLETED = "migration.run.completed"
    RUN_FAILED = "migration.run.failed"
    DDL_DEPLOYED = "migration.ddl.deployed"
    RECON_COMPLETED = "migration.recon.completed"
    ROLLBACK_PERFORMED = "migration.rollback.performed"

    # assessment / intelligence
    ASSESSMENT_COMPLETED = "assessment.completed"

    # connector ecosystem
    CONNECTOR_INSTALLED = "connector.installed"

    # governance
    POLICY_VIOLATED = "governance.policy.violated"

    # integration
    JIRA_SYNCED = "integration.jira.synced"


# Subscribe with this to receive every event.
WILDCARD = "*"


@dataclass(frozen=True)
class DomainEvent:
    """An immutable domain fact.

    ``name`` is normally an ``EventName`` value but kept as ``str`` so adapters
    and plugins can emit their own namespaced events without modifying the core.
    """

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    org_id: Optional[str] = None
    correlation_id: Optional[str] = None
    occurred_at: Optional[str] = None   # ISO-8601, stamped by infra on publish

    @classmethod
    def of(
        cls,
        name: "str | EventName",
        *,
        payload: Optional[dict[str, Any]] = None,
        org_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> "DomainEvent":
        return cls(
            name=name.value if isinstance(name, EventName) else name,
            payload=payload or {},
            org_id=org_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
        )
