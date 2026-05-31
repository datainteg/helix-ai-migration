"""Canonical migration types + connector-kind helpers.

Single source of truth (backend) for the migration_type enum and which
connector kinds / valid connectors each type allows. The frontend mirrors this
shape. The connector PAIR carries the dialects, so we don't enumerate engine
pairs — just intent + shape.
"""

from __future__ import annotations

# connector_type -> kind. Unknown/custom falls back to "db".
KIND_BY_CONNECTOR: dict[str, str] = {
    "postgres": "db", "mysql": "db", "sqlserver": "db", "snowflake": "db",
    "s3": "file", "csv_upload": "file", "excel_upload": "file",
}

DB_CONNECTORS = sorted(k for k, v in KIND_BY_CONNECTOR.items() if v == "db")
FILE_CONNECTORS = sorted(k for k, v in KIND_BY_CONNECTOR.items() if v == "file")


def connector_kind(connector_type: str | None) -> str:
    return KIND_BY_CONNECTOR.get((connector_type or "").lower(), "db")


# migration_type -> spec. source/target_kinds list the allowed connector kinds.
MIGRATION_TYPES: dict[str, dict] = {
    "db_to_db":    {"label": "Database → Database", "source_kinds": ["db"],          "target_kinds": ["db"],   "recon": True},
    "file_to_db":  {"label": "File → Database",     "source_kinds": ["file"],        "target_kinds": ["db"],   "recon": True},
    "db_to_file":  {"label": "Database → File",     "source_kinds": ["db"],          "target_kinds": ["file"], "recon": True},
    "schema_only": {"label": "Schema only",         "source_kinds": ["db"],          "target_kinds": ["db"],   "recon": False},
    "data_only":   {"label": "Data only",           "source_kinds": ["db", "file"],  "target_kinds": ["db"],   "recon": True},
}

VALID_TYPES = set(MIGRATION_TYPES)
DEFAULT_TYPE = "db_to_db"


def normalize_migration_type(value: str | None) -> str:
    """Map any stored value to a valid type. Legacy free-text (e.g.
    'oracle-to-snowflake', 'database') → the safe db_to_db default."""
    v = (value or "").strip().lower()
    return v if v in VALID_TYPES else DEFAULT_TYPE


# The four migration nodes, in their fixed execution order. The human approval
# gate always runs after type_mapper.
STEP_NODES: tuple[str, ...] = (
    "schema_analyst",
    "type_mapper",
    "script_generator",
    "reconciler",
)
_GATE_NODE = "type_mapper"

# Per-type behaviour. `skip_nodes` lists nodes that are present-but-skipped (they
# keep their step_order number). `flags` carries the exact contract keys.
# Anything not listed here falls back to db_to_db (the default / legacy path).
_STEP_PLAN_SPECS: dict[str, dict] = {
    "db_to_db":    {"skip_nodes": set(),               "flags": {"emit_ddl": True,  "emit_data": True,  "direction": "load",   "recon": True}},
    "file_to_db":  {"skip_nodes": set(),               "flags": {"emit_ddl": True,  "emit_data": True,  "direction": "load",   "recon": True}},
    "db_to_file":  {"skip_nodes": set(),               "flags": {"emit_ddl": False, "emit_data": True,  "direction": "unload", "recon": True}},
    "schema_only": {"skip_nodes": {"reconciler"},      "flags": {"emit_ddl": True,  "emit_data": False, "direction": "load",   "recon": False}},
    "data_only":   {"skip_nodes": set(),               "flags": {"emit_ddl": False, "emit_data": True,  "direction": "load",   "recon": True}},
}


def build_step_plan(
    migration_type: str, source_kind: str, target_kind: str
) -> tuple[list[dict], dict]:
    """Build the type-aware step plan + flags for a migration.

    Pure + unit-testable: no I/O, no global state. Returns
    ``(step_plan, flags)`` where:

    * ``step_plan`` is a list of 4 dicts (one per node in STEP_NODES order),
      each EXACTLY ``{"node", "step_order", "skip", "gate_after"}``. step_order
      is contiguous 1..4; skipped nodes keep their order number. gate_after is
      True only on the node the approval gate follows (always ``type_mapper``).
    * ``flags`` is ``{"emit_ddl", "emit_data", "direction", "recon"}``.

    Unknown / None migration_type behaves as db_to_db. source_kind /
    target_kind are accepted for interface symmetry with the contract (and so
    callers always pass the resolved kinds); the per-type spec is what drives
    behaviour.
    """
    mt = normalize_migration_type(migration_type)
    spec = _STEP_PLAN_SPECS.get(mt, _STEP_PLAN_SPECS[DEFAULT_TYPE])
    skip_nodes = spec["skip_nodes"]

    step_plan: list[dict] = []
    for idx, node in enumerate(STEP_NODES, start=1):
        step_plan.append(
            {
                "node": node,
                "step_order": idx,
                "skip": node in skip_nodes,
                "gate_after": node == _GATE_NODE,
            }
        )

    # Return a fresh copy of the flags so callers can mutate without aliasing.
    flags = dict(spec["flags"])
    return step_plan, flags
