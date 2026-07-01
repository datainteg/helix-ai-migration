"""Guard: the migration engine core must stay vendor- and framework-free.

The whole "Any Source -> IR -> Any Target" guarantee rests on the core never
depending on a specific vendor or the web/orchestration frameworks. This test
fails CI if anything under ``migration_engine/`` (excluding tests) imports a
forbidden module — catching architectural drift the moment it happens.
"""

from __future__ import annotations

import re
from pathlib import Path

# Frameworks + vendor SDKs + host packages the pure core must never import.
FORBIDDEN = (
    "fastapi", "starlette", "sqlalchemy", "alembic", "temporalio", "redis",
    "httpx", "requests", "pydantic", "boto3", "snowflake", "ibm_db", "pyodbc",
    "pymysql", "psycopg2", "pandas", "langgraph", "pydantic_ai",
    "app", "backend", "worker", "connectors", "agents",
)

_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)", re.MULTILINE)

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # .../migration_engine


def _source_files() -> list[Path]:
    return [
        p for p in _PACKAGE_ROOT.rglob("*.py")
        if "tests" not in p.relative_to(_PACKAGE_ROOT).parts
    ]


def test_core_has_no_vendor_or_framework_imports():
    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for module in _IMPORT_RE.findall(text):
            top = module.split(".", 1)[0]
            if top in FORBIDDEN:
                rel = path.relative_to(_PACKAGE_ROOT)
                offenders.append(f"{rel}: imports {module!r}")
    assert not offenders, "Core purity violated:\n" + "\n".join(offenders)


def test_purity_scanner_actually_scans_files():
    # Sanity: ensure we're not vacuously passing because no files were found.
    assert len(_source_files()) >= 8
