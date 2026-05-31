"""Class facade for the DB-migration agent chain (A2).

Mirrors HelixBMAD but targets the `MigrationPerNodeWorkflow` Temporal type and
runs alongside BMAD on the same task queue. The workflow id is namespaced
``mig-`` so it never collides with a BMAD ``bmad-`` run.

Unlike HelixBMAD, this starts the workflow by its STRING type name rather than
importing the workflow class. The backend image does not ship the ``worker``
package, so importing ``worker.workflows...`` from FastAPI would raise
ModuleNotFoundError. Temporal can start a workflow by type-name string; the
worker (which has the class registered) executes it.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from agents.helix import HelixBMADResult
from app.services.migration_types import (
    build_step_plan,
    connector_kind,
    normalize_migration_type,
)

MIGRATION_WORKFLOW_TYPE = "MigrationPerNodeWorkflow"


class HelixMigration:
    DEFAULT_TASK_QUEUE = "helix-bmad-task-queue"
    DEFAULT_TEMPORAL_ADDRESS = "localhost:7233"

    def __init__(
        self,
        *,
        project_id: str,
        requirement_id: str,
        organization_id: str | None = None,
        source_connection_id: str | None = None,
        target_connection_id: str | None = None,
        source_connector_type: str | None = None,
        target_connector_type: str | None = None,
        source_config: dict[str, Any] | None = None,
        target_config: dict[str, Any] | None = None,
        in_scope_schemas: list[str] | None = None,
        requirement_text: str = "",
        migration_type: str = "db_to_db",
        workflow_run_id: str | None = None,
        correlation_id: str | None = None,
        temporal_address: str | None = None,
        task_queue: str | None = None,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required")
        if not requirement_id:
            raise ValueError("requirement_id is required")
        self.project_id = project_id
        self.requirement_id = requirement_id
        self.organization_id = organization_id
        self.source_connection_id = source_connection_id
        self.target_connection_id = target_connection_id
        self.source_connector_type = source_connector_type
        self.target_connector_type = target_connector_type
        self.source_config = source_config or {}
        self.target_config = target_config or {}
        self.in_scope_schemas = in_scope_schemas or []
        self.requirement_text = requirement_text or ""
        self.migration_type = normalize_migration_type(migration_type)
        self.workflow_run_id = workflow_run_id or str(uuid4())
        self.correlation_id = correlation_id or self.workflow_run_id
        self.temporal_address = temporal_address or os.getenv(
            "TEMPORAL_ADDRESS", self.DEFAULT_TEMPORAL_ADDRESS
        )
        self.task_queue = task_queue or os.getenv("TEMPORAL_TASK_QUEUE", self.DEFAULT_TASK_QUEUE)

    @property
    def workflow_id(self) -> str:
        # Unique per run so the same requirement can be re-run without colliding
        # with an existing Temporal workflow id.
        return f"mig-{self.project_id}-{self.requirement_id}-{self.workflow_run_id[:8]}"

    def _input_payload(self) -> dict[str, Any]:
        source_kind = connector_kind(self.source_connector_type)
        target_kind = connector_kind(self.target_connector_type)
        step_plan, flags = build_step_plan(
            self.migration_type, source_kind, target_kind
        )
        return {
            "project_id": self.project_id,
            "requirement_id": self.requirement_id,
            "organization_id": self.organization_id,
            "requirement_text": self.requirement_text,
            "workflow_run_id": self.workflow_run_id,
            "correlation_id": self.correlation_id,
            "source_connection_id": self.source_connection_id,
            "target_connection_id": self.target_connection_id,
            "source_connector_type": self.source_connector_type,
            "target_connector_type": self.target_connector_type,
            "source_config": self.source_config,
            "target_config": self.target_config,
            "in_scope_schemas": self.in_scope_schemas,
            # Type-aware migration contract (Step C). These keys are consumed by
            # the worker node activities + per-node workflow.
            "migration_type": self.migration_type,
            "source_kind": source_kind,
            "target_kind": target_kind,
            "emit_ddl": flags["emit_ddl"],
            "emit_data": flags["emit_data"],
            "direction": flags["direction"],
            "recon": flags["recon"],
            "step_plan": step_plan,
        }

    async def start_temporal(self) -> HelixBMADResult:
        """Submit MigrationPerNodeWorkflow to Temporal by type name + return."""
        from temporalio.client import Client

        client = await Client.connect(self.temporal_address)
        handle = await client.start_workflow(
            MIGRATION_WORKFLOW_TYPE,
            self._input_payload(),
            id=self.workflow_id,
            task_queue=self.task_queue,
        )
        return HelixBMADResult(
            workflow_id=self.workflow_id,
            run_id=handle.result_run_id,
            status="started",
            mode="temporal",
            correlation_id=self.correlation_id,
        )
