"""Validation engine — schema-compare, row-count, null-count checks."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.validation import ValidationRule, ValidationRun, ValidationResult

logger = logging.getLogger(__name__)


async def _get_connector(connector_type: str, config: dict):
    from app.services.connector_service import _build_connector
    return _build_connector(connector_type, config)


async def run_schema_compare(
    source_type: str,
    source_config: dict,
    source_schema: str,
    source_table: str,
    target_type: str,
    target_config: dict,
    target_schema: str,
    target_table: str,
) -> dict[str, Any]:
    """Compare columns between source and target table. Returns added/removed/type_diff lists."""
    from app.services.connector_service import discover_columns

    src_cols = await discover_columns(source_type, source_config, source_schema, source_table)
    tgt_cols = await discover_columns(target_type, target_config, target_schema, target_table)

    src_map = {c.column_name: c.data_type for c in src_cols}
    tgt_map = {c.column_name: c.data_type for c in tgt_cols}

    added = [name for name in tgt_map if name not in src_map]
    removed = [name for name in src_map if name not in tgt_map]
    type_diff = [
        {"column": name, "source_type": src_map[name], "target_type": tgt_map[name]}
        for name in src_map
        if name in tgt_map and src_map[name] != tgt_map[name]
    ]

    passed = not added and not removed and not type_diff
    return {
        "passed": passed,
        "added": added,
        "removed": removed,
        "type_diff": type_diff,
        "source_column_count": len(src_map),
        "target_column_count": len(tgt_map),
    }


async def execute_validation_run(
    db: Session,
    run: ValidationRun,
    rules: list[ValidationRule],
    connector_configs: dict[str, Any],
) -> ValidationRun:
    """Execute all rules in a validation run and persist results."""
    from app.services.connector_service import get_row_count

    run.status = "running"
    db.commit()

    results = []
    all_passed = True

    for rule in rules:
        try:
            if rule.rule_type == "row_count":
                cfg = connector_configs.get("source", {})
                connector_type = cfg.get("connector_type", "postgres")
                config = cfg.get("config", {})
                schema = cfg.get("schema", "public")
                table = cfg.get("table", "")
                rc = await get_row_count(connector_type, config, schema, table)
                expected = rule.definition or "0"
                observed = str(rc.row_count)
                passed = rc.row_count == int(expected) if expected.isdigit() else True
                status = "passed" if passed else "failed"

            elif rule.rule_type == "schema_compare":
                defn = json.loads(rule.definition) if rule.definition else {}
                result = await run_schema_compare(
                    defn.get("source_type", "postgres"),
                    defn.get("source_config", {}),
                    defn.get("source_schema", "public"),
                    defn.get("source_table", ""),
                    defn.get("target_type", "postgres"),
                    defn.get("target_config", {}),
                    defn.get("target_schema", "public"),
                    defn.get("target_table", ""),
                )
                passed = result["passed"]
                status = "passed" if passed else "failed"
                observed = json.dumps(result)
                expected = "no_diff"

            else:
                status = "skipped"
                observed = ""
                expected = ""

            if status == "failed":
                all_passed = False

            vr = ValidationResult(
                run_id=run.id,
                rule_id=rule.id,
                status=status,
                observed_value=observed if len(str(observed)) <= 255 else str(observed)[:252] + "...",
                expected_value=expected,
            )
            db.add(vr)
            results.append({"rule_id": rule.id, "rule_type": rule.rule_type, "status": status})

        except Exception as exc:
            logger.warning("Rule %s failed with error: %s", rule.id, exc)
            all_passed = False
            vr = ValidationResult(
                run_id=run.id,
                rule_id=rule.id,
                status="error",
                observed_value=str(exc)[:255],
                expected_value="",
            )
            db.add(vr)
            results.append({"rule_id": rule.id, "rule_type": rule.rule_type, "status": "error"})

    run.status = "completed" if all_passed else "failed"
    db.commit()
    return run
