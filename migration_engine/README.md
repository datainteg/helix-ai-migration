# migration_engine

The deterministic, vendor-neutral **core** of the Enterprise Migration &
Modernization Platform. Contract: **Any Source → Canonical IR → Any Target**.

This package is intentionally **pure**: no FastAPI, no Temporal, no database,
and no source/target vendor SDKs. Vendor logic lives in connector plugins that
implement the SPI defined here. Purity is enforced by a test
(`tests/test_core_purity.py`) so it can't drift.

## Layout

| Module | Responsibility |
|---|---|
| `ir/` | Canonical IR: `types` (vendor-neutral type system), `transforms` (transformation vocabulary), `model` (datasets/jobs/lineage + validation), `version` (schema versioning), `serialize` (lossless JSON round-trip) |
| `graph/` | Dependency + **impact analysis** over IR lineage (blast radius, topological order, cycle detection) |
| `mapping/` | Config-driven, layered **rule engine** (global→org→project) for canonical→target type rendering. Mechanism only; dialect rule sets are supplied as data |
| `events/` | **EventBus** port + in-memory implementation, and the catalog of domain events |
| `spi/` | Connector **v2 capability contracts** (`MetadataProvider`, `JobParser`, `CodeGenerator`, `Deployer`, …) + a versioned `ConnectorRegistry` |

## Design rules

1. **No vendor names in this package.** Concrete dialects/connectors implement
   the SPI and supply rule sets as config.
2. **Version everything** that crosses a boundary — `ir_version` and
   `contract_version` are negotiated at registration.
3. **Never guess silently.** Unmapped types/transforms are flagged
   (`MappingResult.matched == False`, `TypeKind.UNKNOWN` carries the raw type)
   so the Assessment engine can count them as manual effort.

## Tests

```bash
# from the repo root, using the project venv
.venv/Scripts/python -m pytest migration_engine/tests -q   # Windows
.venv/bin/python -m pytest migration_engine/tests -q       # POSIX
```

No infrastructure required — the core runs on Python alone.
