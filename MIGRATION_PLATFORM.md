# Migration Platform — Developer Onboarding & Handoff

> **Read this first.** It's the "start here" for continuing the Enterprise
> Migration & Modernization Platform work (the `migration_engine/` + `plugins/`
> effort), including on a fresh machine / Linux.

Turning `helix-ai-migration` into a **commercial, enterprise-grade Data
Migration & Modernization Platform** specialized in **IBM DataStage / SAS /
legacy (DB2) → cloud (Snowflake / Databricks / Airflow)** migrations.

**North star:** measurably cut migration cycle time and lift productivity with
AI — with **living docs, validation, and reconciliation** as first-class quality
gates and **Jira as the system of record**. Core principle:
**`Any Source → Canonical IR → Any Target`** (add systems as plugins; never
touch the core).

---

## Current status

- **Branch:** `feat/migration-engine-foundation`
- **Commits so far:**
  - `feat(migration-engine)` — deterministic vendor-neutral core (Phase 0)
  - `feat(plugins)` — DB2 source + Snowflake target (first end-to-end slice)
- **Tests:** **62 passing**, runs in ~0.2s, **Python only — no Docker/DB needed**
- **Full architecture & roadmap:** [`docs/ARCHITECTURE_PLAN.md`](docs/ARCHITECTURE_PLAN.md)
  (the approved plan — Parts A & B, 15 deliverables + enterprise review + phases)

What already works: a real DB2/Bedrock table description is parsed into the
canonical IR and generated into correct **Snowflake DDL**, with unmapped types
flagged (never silently guessed) — see the demo below.

---

## What's built (new code)

```
migration_engine/          # PURE, vendor-neutral core (no FastAPI/Temporal/DB/vendor imports)
  ir/                      # canonical types, transforms, model, versioning, JSON serialization
  graph/                   # dependency + impact analysis (blast radius, topo order, cycles)
  mapping/                 # config-driven layered type-mapping RULE ENGINE (mechanism only)
  events/                  # EventBus port + in-memory impl + domain event catalog
  spi/                     # connector v2 capability contracts + versioned registry
  tests/                   # 48 tests incl. a core-purity guard
  README.md

plugins/                   # vendor plugins implementing the SPI (depend on the core)
  db2/                     # DB2 native type parser + DB2Source (MetadataProvider)
  snowflake/               # Snowflake type rules + DDL generator (CodeGenerator)
  tests/                   # 14 tests incl. registry-driven end-to-end DB2 -> IR -> Snowflake
```

The pre-existing app (backend / worker / frontend / connectors / agents) is the
**enterprise shell** we're evolving — see the repo `README.md` and `DEPLOY.md`.

---

## Setup

Requires **Python 3.10+** (project targets 3.11) and, for the full stack,
**Docker + Docker Compose**.

### A) Engine + plugins (pure Python — no infra) ✅ works today

```bash
# from the repo root: helix-ai-migration/
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\Activate.ps1       # Windows PowerShell
pip install pytest

# run the whole migration-engine + plugins suite
PYTHONPATH=. python -m pytest migration_engine/tests plugins/tests -q
```

`.venv/` is git-ignored. The core has **zero third-party dependencies** — only
`pytest` is needed to run the tests.

### B) Full stack (backend + worker + frontend) — needs Docker (best on Linux)

On Linux Docker runs natively (no WSL). See [`DEPLOY.md`](DEPLOY.md) for the full
guide. Quick version:

```bash
./scripts/generate-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose up -d
# open http://localhost:3000/setup/first-admin
```

Backend Python deps live in `backend/requirements.txt` and
`worker/requirements.txt`; the frontend uses `frontend/package.json`.

---

## The end-to-end slice (what it does today)

A DB2 catalog description (mirroring the real `DPE-1369` "Home fixtures →
Snowflake" ticket) → canonical IR → **generated Snowflake DDL**:

```sql
-- WARNING: manual type mapping required for column(s): LEGACY_LOC
CREATE OR REPLACE TABLE "ANALYTICS"."HOME_FIXTURES" (
    "FIXTURE_ID" NUMBER(18,0) NOT NULL,
    "ACCOUNT_NO" CHAR(11) NOT NULL,
    "DESCRIPTION" VARCHAR(240),
    "BALANCE" NUMBER(15,2),
    "OPENED_AT" TIMESTAMP_NTZ,
    "LEGACY_LOC" unknown(ROWID),          -- flagged, not guessed
    PRIMARY KEY ("FIXTURE_ID")
);
```

See `plugins/tests/test_end_to_end.py` for the runnable version (resolves the
source + target through the capability registry, not a hard-coded pair).

---

## Design principles (do not break these)

1. **Core purity** — nothing under `migration_engine/` imports a vendor SDK or a
   framework (FastAPI/Temporal/DB). Enforced by `tests/test_core_purity.py`.
   Vendor logic lives in `plugins/`.
2. **Any Source → IR → Any Target** — sources parse *into* the IR; targets
   generate *from* it. Adding a system is N+M plugins, never N×M.
3. **Config over code** — type/transform/naming rules are data (the rule
   engine), so new dialects/orgs need config, not core edits.
4. **Never guess silently** — unmapped types/transforms are flagged
   (`MappingResult.matched == False`, `TypeKind.UNKNOWN` keeps the raw type) so
   the Assessment engine can count them as manual effort.
5. **Version everything** that crosses a boundary — `ir_version` and
   `contract_version` are negotiated when a connector registers.

---

## Roadmap / next steps

Next pure, Docker-free pieces (highest value first — all testable now):

1. **Assessment engine** — complexity, **automation % vs manual %**, unmapped
   list, risk & effort. Reuses IR + mapping coverage + transform determinism.
   The commercial differentiator; directly quantifies "time saved."
2. **Reconciliation engine** — schema + row-count + checksum + column-stat diffs
   (the validation/recon quality gate). Pure logic now; live-DB exec wires later.
3. **Living-docs generator** — IR → reviewable migration doc (mapping table,
   lineage, decisions, recon evidence). Reuse the BMAD doc agent to narrate.
4. **Backend wiring** (needs Docker) — `MigrationUnit` / `MigrationRun` models +
   Alembic + API + Temporal workflow; Jira sync.
5. **DataStage `.dsx`/`.isx` parser** (Phase 2) — needs sample exports from the
   real environment; parse → IR jobs → visual graph + impact analysis.

Full phased plan (Phase 0–5) is in [`docs/ARCHITECTURE_PLAN.md`](docs/ARCHITECTURE_PLAN.md) §15 / B6.

---

## Continuing with Claude Code (on the new machine)

1. Clone the repo and check out the branch:
   ```bash
   git clone https://github.com/datainteg/helix-ai-migration.git
   cd helix-ai-migration
   git checkout feat/migration-engine-foundation
   ```
2. Do **Setup A** above and confirm `62 passed`.
3. Open Claude Code in the repo and say, e.g.:
   > "Read `MIGRATION_PLATFORM.md` and `docs/ARCHITECTURE_PLAN.md`, then continue
   > Phase 1 — build the **Assessment engine** next (roadmap item 1)."
4. Keep the working rhythm: build a pure module + tests, run the suite green,
   then commit. Bring up Docker (Setup B) when starting the backend wiring.

> Tip: the architecture plan is the source of truth. If scope questions come up,
> reconcile against it before coding.
