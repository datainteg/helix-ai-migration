"""DB-migration agent-chain activities.

A2-1 SKELETON: these four activities are deterministic ECHO stubs that return
canned results in the exact dict shape the BMAD node activities return, so the
shared `persist_workflow_step_activity` / per-node workflow scaffold work
verbatim. Later milestones replace each body with the real implementation:
  - schema_analyst   -> deterministic connector introspection (A2-2)
  - type_mapper      -> LLM type/semantic mapping (A2-3)
  - script_generator -> LLM + templates DDL/data/rollback SQL (A2-4)
  - reconciler       -> deterministic row-count/checksum/sample recon (A2-5)

Return shape (matches worker/activities/bmad_node_activities.py):
  {agent, skill, success, mode, errors, artifact_path, parsed}
"""
from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


def _echo(agent: str, skill: str, parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent": agent,
        "skill": skill,
        "success": True,
        "mode": "echo",
        "errors": [],
        "artifact_path": None,
        "parsed": parsed,
    }


@activity.defn
def schema_analyst_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    logger.info("migration: schema_analyst (echo) for project=%s", input_data.get("project_id"))
    return _echo(
        "schema_analyst",
        "migration-analyze-schema",
        {
            "summary": "echo: source schema analyzed",
            "source_connector_type": input_data.get("source_connector_type"),
            "schemas": [],
            "table_count": 0,
        },
    )


@activity.defn
def type_mapper_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    logger.info("migration: type_mapper (echo) for project=%s", input_data.get("project_id"))
    return _echo(
        "type_mapper",
        "migration-map-types",
        {
            "summary": "echo: type mapping proposed",
            "target_connector_type": input_data.get("target_connector_type"),
            "approval_required": True,
            "ambiguous_mappings": [],
        },
    )


@activity.defn
def script_generator_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    logger.info("migration: script_generator (echo) for project=%s", input_data.get("project_id"))
    return _echo(
        "script_generator",
        "migration-generate-scripts",
        {
            "summary": "echo: migration scripts generated",
            "manual_steps": [],
            "execution_enabled": False,
        },
    )


@activity.defn
def reconciler_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    logger.info("migration: reconciler (echo) for project=%s", input_data.get("project_id"))
    return _echo(
        "reconciler",
        "migration-reconcile",
        {
            "summary": "echo: reconciliation complete",
            "verified_pct": 100.0,
            "tables_checked": 0,
        },
    )
