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

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from temporalio import activity

from agents.runtime.llm_client import call_llm

logger = logging.getLogger(__name__)

# Cost-bounding caps for source introspection (A2-2). A migration source can
# have hundreds of schemas/tables; introspecting all of them up front would
# blow the activity timeout and the snapshot payload size. We cap and flag
# `truncated=True` so downstream agents (type_mapper) know the model is partial.
_MAX_SCHEMAS = 25
_MAX_TABLES = 200

# Postgres-family system schemas to skip during introspection.
_SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


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


def _is_skippable_schema(name: str) -> bool:
    """True for Postgres-family system schemas that should never be migrated."""
    if not name:
        return True
    return name in _SYSTEM_SCHEMAS or name.startswith("pg_")


async def _introspect_source(
    connector_type: str,
    config: dict[str, Any],
    in_scope: list[str],
) -> dict[str, Any]:
    """Fan out connector introspection into a normalized source-schema model.

    Runs schema -> table -> column/row-count discovery via the worker-importable
    `app.services.connector_service` async funcs. Bounded by `_MAX_SCHEMAS` /
    `_MAX_TABLES`; sets `truncated=True` when either cap clips the result.
    """
    from app.services import connector_service

    truncated = False

    schema_infos = await connector_service.discover_schemas(connector_type, config)
    schema_names: list[str] = []
    in_scope_set = {s for s in in_scope if s}
    for si in schema_infos:
        name = si.schema_name
        if _is_skippable_schema(name):
            continue
        if in_scope_set and name not in in_scope_set:
            continue
        schema_names.append(name)

    if len(schema_names) > _MAX_SCHEMAS:
        schema_names = schema_names[:_MAX_SCHEMAS]
        truncated = True

    schemas_model: list[dict[str, Any]] = []
    table_count = 0
    column_count = 0
    tables_seen = 0

    for schema_name in schema_names:
        if tables_seen >= _MAX_TABLES:
            truncated = True
            break

        table_infos = await connector_service.discover_tables(connector_type, config, schema_name)
        tables_model: list[dict[str, Any]] = []
        for ti in table_infos:
            if tables_seen >= _MAX_TABLES:
                truncated = True
                break
            tables_seen += 1
            table_name = ti.table_name

            col_infos = await connector_service.discover_columns(
                connector_type, config, schema_name, table_name
            )
            columns_model: list[dict[str, Any]] = []
            for ci in col_infos:
                col: dict[str, Any] = {
                    "name": ci.column_name,
                    "type": ci.data_type,
                    "nullable": ci.is_nullable,
                }
                # ColumnInfo only carries precision/scale on connectors that
                # populate them; include only when present so the model stays
                # connector-agnostic.
                precision = getattr(ci, "precision", None)
                scale = getattr(ci, "scale", None)
                if precision is not None:
                    col["precision"] = precision
                if scale is not None:
                    col["scale"] = scale
                columns_model.append(col)

            column_count += len(columns_model)

            row_count: int | None
            try:
                rc = await connector_service.get_row_count(
                    connector_type, config, schema_name, table_name
                )
                row_count = rc.row_count
            except Exception as exc:  # noqa: BLE001 — one bad table must not abort
                logger.warning(
                    "schema_analyst: row count failed for %s.%s: %s",
                    schema_name,
                    table_name,
                    exc,
                )
                row_count = None

            tables_model.append(
                {
                    "table": table_name,
                    "row_count": row_count,
                    "columns": columns_model,
                }
            )

        table_count += len(tables_model)
        schemas_model.append({"schema": schema_name, "tables": tables_model})

    return {
        "source_connector_type": connector_type,
        "schemas": schemas_model,
        "table_count": table_count,
        "column_count": column_count,
        "truncated": truncated,
    }


def _failure_result(errors: list[str], summary: str) -> dict[str, Any]:
    return {
        "agent": "schema_analyst",
        "skill": "migration-analyze-schema",
        "success": False,
        "mode": "introspect",
        "errors": errors,
        "artifact_path": None,
        "parsed": {
            "summary": summary,
            "schema_count": 0,
            "table_count": 0,
            "column_count": 0,
            "truncated": False,
        },
    }


def _write_schema_artifact(project_id: str, model: dict[str, Any]) -> str | None:
    """Write the analyzed-source-schema artifact (markdown wrapping JSON).

    Returns the absolute path string, or None if the artifact store is
    unavailable / the write fails — a failed artifact write must NOT fail the
    whole activity.
    """
    try:
        from agents.runtime.artifact_store import write_artifact

        body = (
            "# Analyzed Source Schema\n\n"
            "Deterministic source-schema introspection produced by the "
            "`schema_analyst` migration agent.\n\n"
            "```json\n" + json.dumps(model, indent=2, sort_keys=True) + "\n```\n"
        )
        artifact = write_artifact(
            project_id=project_id,
            agent_code="schema_analyst",
            skill="migration-analyze-schema",
            filename="analyzed-source-schema",
            body=body,
            frontmatter={
                "source_connector_type": model.get("source_connector_type"),
                "table_count": model.get("table_count"),
                "column_count": model.get("column_count"),
                "truncated": model.get("truncated"),
            },
            phase="analysis",
        )
        return str(artifact.path)
    except Exception as exc:  # noqa: BLE001 — artifact write is best-effort
        logger.warning("schema_analyst: artifact write failed: %s", exc)
        return None


def _persist_snapshot(
    input_data: dict[str, Any],
    model: dict[str, Any],
) -> None:
    """Insert one SourceSchemaSnapshot row. Best-effort: logs + swallows errors."""
    try:
        from worker.db.session import SessionLocal
        from app.models.schema_snapshot import SourceSchemaSnapshot

        source_ref = (
            input_data.get("source_connector_type")
            or input_data.get("source_connection_id")
            or "source"
        )
        db = SessionLocal()
        try:
            db.add(
                SourceSchemaSnapshot(
                    organization_id=input_data.get("organization_id"),
                    project_id=input_data.get("project_id"),
                    source_ref=source_ref,
                    payload=json.dumps(model),
                    table_count=model.get("table_count", 0),
                    column_count=model.get("column_count", 0),
                    taken_at=datetime.now(timezone.utc),
                    notes="schema_analyst introspection"
                    + (" (truncated)" if model.get("truncated") else ""),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — snapshot persistence is best-effort
        logger.warning("schema_analyst: snapshot persistence failed: %s", exc)


@activity.defn
def schema_analyst_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    project_id = input_data.get("project_id")
    logger.info("migration: schema_analyst (introspect) for project=%s", project_id)

    connector_type = input_data.get("source_connector_type")
    config = input_data.get("source_config")
    in_scope = input_data.get("in_scope_schemas") or []

    if not connector_type or not config:
        return _failure_result(
            ["source connector/config not provided"],
            "schema introspection skipped: missing source connector/config",
        )

    try:
        # Introspection is blocking (psycopg2 in a thread pool) and can exceed
        # the 60s heartbeat on a large DB, so wrap the asyncio fan-out in
        # _run_with_heartbeats. detail_prefix surfaces in Temporal heartbeats.
        from worker.activities.bmad_node_activities import _run_with_heartbeats

        model = _run_with_heartbeats(
            lambda: asyncio.run(_introspect_source(connector_type, config, in_scope)),
            detail_prefix="schema_analyst:introspect",
        )
    except Exception as exc:  # noqa: BLE001 — connection / discovery failure
        logger.exception("schema_analyst: introspection failed for project=%s", project_id)
        return _failure_result(
            [str(exc)],
            f"schema introspection failed: {exc}",
        )

    artifact_path = _write_schema_artifact(str(project_id), model) if project_id else None
    _persist_snapshot(input_data, model)

    schema_count = len(model.get("schemas", []))
    table_count = model.get("table_count", 0)
    column_count = model.get("column_count", 0)
    truncated = bool(model.get("truncated"))
    summary = (
        f"Introspected {schema_count} schema(s), {table_count} table(s), "
        f"{column_count} column(s) from {connector_type}"
        + (" (truncated)" if truncated else "")
    )

    return {
        "agent": "schema_analyst",
        "skill": "migration-analyze-schema",
        "success": True,
        "mode": "introspect",
        "errors": [],
        "artifact_path": artifact_path,
        "parsed": {
            "summary": summary,
            "schema_count": schema_count,
            "table_count": table_count,
            "column_count": column_count,
            "truncated": truncated,
        },
    }


# Bound the prompt size: a source DB can carry hundreds of tables, but the
# type-mapper only needs enough samples to enumerate distinct source types, so
# we cap the compact representation at the first N tables and flag truncation.
_MAX_PROMPT_TABLES = 40

# Cap the ambiguous-mappings list before it lands in WorkflowStep.parsed_output_json
# (JSONB) so a chatty model can't bloat the row.
_MAX_AMBIGUOUS = 50


def _type_mapper_failure(errors: list[str], summary: str) -> dict[str, Any]:
    """Standard-shape failure result for the type_mapper node."""
    return {
        "agent": "type_mapper",
        "skill": "migration-map-types",
        "success": False,
        "mode": "llm",
        "errors": errors,
        "artifact_path": None,
        "parsed": {
            "summary": summary,
            "approval_required": True,
            "mapping_count": 0,
            "ambiguous_mappings": [],
            "truncated": False,
        },
    }


def _load_latest_source_model(project_id: str) -> dict[str, Any] | None:
    """Return the parsed payload of the most recent SourceSchemaSnapshot, or None.

    None means either no snapshot row exists or its payload failed to parse —
    callers treat both as "run SchemaAnalyst first".
    """
    from worker.db.session import SessionLocal
    from app.models.schema_snapshot import SourceSchemaSnapshot

    db = SessionLocal()
    try:
        snapshot = (
            db.query(SourceSchemaSnapshot)
            .filter(SourceSchemaSnapshot.project_id == project_id)
            .order_by(SourceSchemaSnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            return None
        try:
            model = json.loads(snapshot.payload)
        except Exception as exc:  # noqa: BLE001 — malformed payload is non-fatal
            logger.warning("type_mapper: snapshot payload parse failed: %s", exc)
            return None
        return model if isinstance(model, dict) else None
    finally:
        db.close()


def _compact_schema_lines(model: dict[str, Any]) -> tuple[list[str], bool]:
    """Flatten the source schema model into compact per-table lines.

    Emits one line per table: `schema.table: col1 TYPE [NULL], col2 TYPE, ...`.
    Caps at `_MAX_PROMPT_TABLES`; returns (lines, truncated).
    """
    lines: list[str] = []
    truncated = bool(model.get("truncated"))
    emitted = 0
    total_tables = 0

    for schema in model.get("schemas") or []:
        schema_name = schema.get("schema") or ""
        for table in schema.get("tables") or []:
            total_tables += 1
            if emitted >= _MAX_PROMPT_TABLES:
                continue
            table_name = table.get("table") or ""
            col_parts: list[str] = []
            for col in table.get("columns") or []:
                name = col.get("name") or ""
                ctype = col.get("type") or "?"
                # `nullable` is True when the column accepts NULL.
                null_flag = " [NULL]" if col.get("nullable") else ""
                col_parts.append(f"{name} {ctype}{null_flag}")
            lines.append(f"{schema_name}.{table_name}: " + ", ".join(col_parts))
            emitted += 1

    if total_tables > emitted:
        truncated = True
        lines.append(f"... and {total_tables - emitted} more tables omitted")

    return lines, truncated


def _write_type_mapping_artifact(
    project_id: str,
    summary: str,
    mappings: list[dict[str, Any]],
    ambiguous: list[dict[str, Any]],
    source_connector_type: str | None,
    target: str,
) -> str | None:
    """Write the type-mapping artifact (markdown). Best-effort; None on failure."""
    try:
        from agents.runtime.artifact_store import write_artifact

        lines = [
            "# Type Mapping\n",
            f"LLM-proposed source→target type mapping ({source_connector_type or '?'} → {target}).\n",
            "## Summary\n",
            summary + "\n",
            "## Mappings\n",
            "| Source type | Target type | Note |",
            "| --- | --- | --- |",
        ]
        for m in mappings:
            src = str(m.get("source_type", "")).replace("|", "\\|")
            tgt = str(m.get("target_type", "")).replace("|", "\\|")
            note = str(m.get("note", "")).replace("|", "\\|")
            lines.append(f"| {src} | {tgt} | {note} |")
        if not mappings:
            lines.append("| _(none returned)_ | | |")

        lines.append("\n## Ambiguous / needs review\n")
        if ambiguous:
            for a in ambiguous:
                lines.append(
                    f"- `{a.get('table', '?')}.{a.get('column', '?')}` "
                    f"({a.get('source_type', '?')} → {a.get('target_type', '?')}): "
                    f"{a.get('reason', '')}"
                )
        else:
            lines.append("_None flagged._")

        body = "\n".join(lines) + "\n"
        artifact = write_artifact(
            project_id=project_id,
            agent_code="type_mapper",
            skill="migration-map-types",
            filename="type-mapping",
            body=body,
            frontmatter={
                "source_connector_type": source_connector_type,
                "target_connector_type": target,
                "mapping_count": len(mappings),
                "ambiguous_count": len(ambiguous),
                "approval_required": True,
            },
            phase="planning",
        )
        return str(artifact.path)
    except Exception as exc:  # noqa: BLE001 — artifact write is best-effort
        logger.warning("type_mapper: artifact write failed: %s", exc)
        return None


@activity.defn
def type_mapper_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    project_id = input_data.get("project_id")
    logger.info("migration: type_mapper (llm) for project=%s", project_id)

    # 1. Load the latest source-schema snapshot.
    model = _load_latest_source_model(project_id)
    if model is None:
        return _type_mapper_failure(
            ["no source schema snapshot found; run SchemaAnalyst first"],
            "type mapping skipped: no source schema snapshot found",
        )

    source_connector_type = (
        model.get("source_connector_type") or input_data.get("source_connector_type")
    )
    target = input_data.get("target_connector_type") or "postgres"

    # 2. Build a bounded compact representation of the source schema.
    compact_lines, truncated = _compact_schema_lines(model)
    compact_text = "\n".join(compact_lines) if compact_lines else "(no tables)"

    # 3. Compose prompts.
    system_prompt = (
        "You are a senior database migration engineer. Map source column data "
        "types to the target database's equivalent types. Be precise about "
        "precision/scale, identity/sequences, and lossy or ambiguous conversions. "
        "Respond with STRICT JSON only."
    )
    user_prompt = (
        f"Source: {source_connector_type}. Target: {target}.\n"
        f"Source schema:\n{compact_text}\n\n"
        'Return JSON: {"mappings":[{"source_type":"...","target_type":"...","note":"..."}], '
        '"ambiguous_mappings":[{"table":"...","column":"...","source_type":"...",'
        '"target_type":"...","reason":"..."}], "summary":"..."}'
    )

    # 4. Call the LLM, wrapped so Temporal keeps heartbeating during the (possibly
    #    >60s) blocking provider call.
    from worker.activities.bmad_node_activities import _run_with_heartbeats

    result = _run_with_heartbeats(
        lambda: call_llm(
            "type_mapper",
            system_prompt,
            user_prompt,
            org_id=input_data.get("organization_id"),
        ),
        "type_mapper",
    )

    if result is None:
        return _type_mapper_failure(
            ["LLM call failed (provider/key/API error)"],
            "type mapping failed: LLM call returned no result",
        )

    # Normalize. The model may return the full JSON schema, or — if it ignored the
    # instruction — just `{"summary": "<raw text>"}`. Either way we succeed.
    mappings = result.get("mappings") if isinstance(result, dict) else []
    if not isinstance(mappings, list):
        mappings = []
    ambiguous = result.get("ambiguous_mappings") if isinstance(result, dict) else []
    if not isinstance(ambiguous, list):
        ambiguous = []
    summary = (result.get("summary") if isinstance(result, dict) else None) or (
        str(result)[:300]
    )

    # 5. The chain always gates after this node.
    approval_required = True

    # Cap ambiguous list before it is persisted into JSONB.
    ambiguous = ambiguous[:_MAX_AMBIGUOUS]

    # 6. Write the type-mapping artifact (best-effort).
    artifact_path = (
        _write_type_mapping_artifact(
            str(project_id),
            summary,
            mappings,
            ambiguous,
            source_connector_type,
            target,
        )
        if project_id
        else None
    )

    # 7. Return the standard result shape.
    return {
        "agent": "type_mapper",
        "skill": "migration-map-types",
        "success": True,
        "mode": "llm",
        "errors": [],
        "artifact_path": artifact_path,
        "parsed": {
            "summary": summary,
            "approval_required": approval_required,
            "mapping_count": len(mappings),
            "ambiguous_mappings": ambiguous,
            "truncated": truncated,
        },
    }


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
